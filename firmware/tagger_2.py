# =============================================================================
# Laser Dual - Tagger 2 (Player 2) firmware (MicroPython, ESP32-WROOM-32E)
#
# Each tagger/vest set has its own ESP32 that:
#   - fires NEC-encoded IR bursts when the trigger is held,
#   - decodes hits from the two IR receivers on the vest,
#   - drives the 4-LED health bar, 2 target LEDs and a 4-digit 7-segment
#     display (cells left),
#   - reports its status to the control unit over ESP-NOW.
#
# Role per game mode:
#   0 Health:   two-player match; HP drops by the opponent tagger's damage.
#   1 Aiming:   Tagger 2 is the stationary target board: one random target
#               LED is lit, and each hit on it scores a point and moves the
#               target. Tagger 1 is the shooter.
#   2 Showdown: unlimited cells; one hit ends the round.
#
# tagger_1.py and tagger_2.py share the same structure. Differences:
#   - display pin mapping
#   - argument order of GameLogic.set_params (each tagger treats itself as
#     "tagger_1" and the opponent as "tagger_2")
#   - Aiming mode behavior (shooter vs. target board)
#
# Message protocol: see docs/esp-now-message-format.pdf
# =============================================================================

from machine import Pin, Timer
import network
import espnow
import time
from ir_tx.nec import NEC        # Third-party: peterhinch/micropython_ir (MIT)
from ir_rx.nec import NEC_8      # Third-party: peterhinch/micropython_ir (MIT)
import urandom
from display.display import disp7S   # 7-segment driver from the UI subsystem
##########################################################################
# NOTE: The two IR receivers cannot be serviced by interrupts at the same
# time; a burst that reaches both receivers at once may not be decoded.
##########################################################################

# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
TRIGGER_PIN = 25
TRIGGER_HOLD_INTERVAL = 500

RELOAD_PIN = 33
END_PIN = 32
DEBOUNCE_DELAY = 100        # ms; shared by the Reload and End buttons

trigger_held = False
last_pressed_time_1 = 0     # Timestamp (ms) of the last accepted button press

# ---------------------------------------------------------------------------
# IR and LEDs
# GPIO34/35 are wired for two more receivers on the PCB but are unused.
# ---------------------------------------------------------------------------
IR_RECV1= Pin(36, Pin.IN)   # Vest IR receiver 1
IR_RECV2= Pin(39, Pin.IN)   # Vest IR receiver 2
IR_TRANSMIT= Pin(14, Pin.OUT, value = 0)   # Tagger IR LED (38 kHz carrier)
LED_1= Pin(18, Pin.OUT) # Health bar LED 1
LED_2= Pin(5, Pin.OUT)  # Health bar LED 2
LED_3= Pin(17, Pin.OUT) # Health bar LED 3
LED_4= Pin(16, Pin.OUT) # Health bar LED 4
LED_5= Pin(23, Pin.OUT) # Target LED 1 (next to IR receiver 1)
LED_6= Pin(22, Pin.OUT) # Target LED 2 (next to IR receiver 2)
LED_HEALTH= [LED_1, LED_2, LED_3, LED_4]
LED_TARG= [LED_5, LED_6]

# 4-digit 7-segment display (driven through a 74HC595 shift register)
pin1= Pin(12, Pin.OUT)      # Digit 1 select
pin2= Pin(13, Pin.OUT)      # Digit 2 select
pin3= Pin(2, Pin.OUT)       # Digit 3 select
pin4= Pin(15, Pin.OUT)      # Digit 4 select
pin5= Pin(26, Pin.OUT)      # Shift register latch
pin6= Pin(27, Pin.OUT)      # Shift register clock
pin7= Pin(21, Pin.OUT)      # Shift register data

# ---------------------------------------------------------------------------
# ESP-NOW setup (station interface active, not connected to an AP)
# ---------------------------------------------------------------------------
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
e = espnow.ESPNow()
e.active(True)
peer= b'\x84\xf7\x03\xe2\x9e\x58'  # Control unit MAC address
e.add_peer(peer)

# ---------------------------------------------------------------------------
# Interrupt handlers
# ---------------------------------------------------------------------------
def reload_pressed_handler(pin):
    # Reload button IRQ (falling edge) with time-based debounce
    global game_logic
    global last_pressed_time_1
    current_time = time.ticks_ms()
    if current_time - last_pressed_time_1 > DEBOUNCE_DELAY:
        print("reload pressed")
        game_logic.handle_reload_btn()
        last_pressed_time_1 = current_time

def end_pressed_handler(pin):
    # End button IRQ: ask the control unit to end the game
    global last_pressed_time_1
    current_time = time.ticks_ms()
    if current_time - last_pressed_time_1 > DEBOUNCE_DELAY:
        print("end pressed")
        game_logic.handle_end_btn()
        last_pressed_time_1 = current_time

def esp_recv(e):
    # ESP-NOW receive callback: parse "<type> <args...>" from the control unit
    global game_logic
    mac, msg_encoded = e.irecv(0)
    if mac is None:
        return

    if msg_encoded:
        msg = msg_encoded.decode()
        print(mac, msg)
        data = msg.split()
        if data:
            if data[0] == '0':
                # [0] Initialization: "0 <mode> <tag1> <tag2> <rounds>"
                print("===========Initialize==========")
                game_logic.set_params(int(data[1]), int(data[2]), int(data[3]), int(data[4]))
            elif data[0] == '1':
                # [1] Game conclusion
                game_logic.handle_game_conclusion()
            elif data[0] == '4':
                # [4] Round start
                game_logic.handle_round_start(int(data[1]))
            elif data[0] == '5':
                # [5] Round end
                game_logic.handle_round_end(int(data[1]))

# IR receive callbacks (called by NEC_8 after a valid frame is decoded)
def ir_recv(data, addr, ctrl):
    global game_logic
    print('IR recevied: data {:02x} addr {:04x}'.format(data, addr))
    game_logic.handle_ir_hit()

def ir_recv_1(data, addr, ctrl):
    # Hit on IR receiver 1
    global game_logic
    print('IR recevied: data {:02x} addr {:04x}'.format(data, addr))
    game_logic.handle_ir_hit()

def ir_recv_2(data, addr, ctrl):
    # Hit on IR receiver 2
    global game_logic
    print('IR recevied: data {:02x} addr {:04x}'.format(data, addr))
    game_logic.handle_ir_hit()

def aim_func(data, addr, ctrl):
    # Callback for a receiver whose target is not lit (hit is ignored)
    print('IR recevied, Not Activated: data {:02x} addr {:04x}'.format(data, addr))

RECV= [IR_RECV1, IR_RECV2]
ir_tx = NEC(IR_TRANSMIT)
# IR decoders are created in GameLogic.set_params once the game mode is known
ir_rx1 = None
ir_rx2 = None
RECV_RX= [ir_rx1, ir_rx2]

class GameLogic:
    def __init__(self):
        class Player():
            # Local player state.
            # hp: health bar (0-4), cl: cells (shots) left, rl: cells after reload
            # Each preset also sets the fire interval and reload time (ms) on
            # the enclosing GameLogic.
            def __init__(self, tagger_id, outer_class):
                self.tg = tagger_id
                self.hp = 4
                self.cl = -1
                self.rl = -1
                if self.tg == 1:        # SWIFT: fast, many cells
                    self.cl = 15
                    self.rl = 15
                    outer_class.TRIGGER_HOLD_INTERVAL = 300
                    outer_class.RELOAD_INTERVAL = 1000
                elif self.tg == 2:      # PULSE: balanced
                    self.cl = 8
                    self.rl = 8
                    outer_class.TRIGGER_HOLD_INTERVAL = 560
                    outer_class.RELOAD_INTERVAL = 2000
                elif self.tg == 3:      # NOVA: slow, high damage
                    self.cl = 2
                    self.rl = 2
                    outer_class.TRIGGER_HOLD_INTERVAL = 1200
                    outer_class.RELOAD_INTERVAL = 4000

            def set_params(self, tagger_id, outer_class):
                # Same as __init__, plus mode-specific overrides
                self.tg = tagger_id
                self.hp = 4
                self.cl = -1
                self.rl = -1
                if self.tg == 1:
                    self.cl = 15
                    self.rl = 15
                    outer_class.TRIGGER_HOLD_INTERVAL = 300
                    outer_class.RELOAD_INTERVAL = 1000
                elif self.tg == 2:
                    self.cl = 8
                    self.rl = 8
                    outer_class.TRIGGER_HOLD_INTERVAL = 560
                    outer_class.RELOAD_INTERVAL = 2000
                elif self.tg == 3:
                    self.cl = 2
                    self.rl = 2
                    outer_class.TRIGGER_HOLD_INTERVAL = 1200
                    outer_class.RELOAD_INTERVAL = 4000

                # Showdown mode: fixed fire interval of 1 s for both players
                if outer_class.game_mode == 2:
                    outer_class.TRIGGER_HOLD_INTERVAL = 1000

                # Aiming mode: hp is reused as the hit counter (score)
                if outer_class.game_mode == 1:
                    self.hp = 0

        self.game_mode = -1
        self.tagger_1 = -1              # This tagger's preset
        self.tagger_2_demage = 0        # HP lost per hit (opponent's damage)
        self.rnd = -1
        self.curr_round = -1
        self.TRIGGER_HOLD_INTERVAL =100 # Minimum time between shots (ms)
        self.RELOAD_INTERVAL = 1000     # Reload lockout time (ms)
        self.game_conclusion = False
        self.round_end = False
        self.player_1 = Player(0, self)

    def set_params(self, game_mode, tagger_2, tagger_1, rnd):
        # Apply the [0] Initialization message. The message lists Player 1's
        # preset first, so the order is swapped here: inside this file
        # tagger_1 = this tagger's preset, tagger_2 = opponent's preset.
        global RECV_RX, ir_rx1, ir_rx2
        self.game_mode = game_mode
        self.tagger_1 = tagger_1
        self.tagger_2_demage = 0
        self.rnd = rnd
        self.curr_round = 0
        self.TRIGGER_HOLD_INTERVAL = 100
        self.game_conclusion = False
        self.round_end = False

        # Damage taken per hit depends on the opponent's tagger.
        # 0 means no opponent preset (Showdown): one hit removes all 4 HP.
        if tagger_2 == 1:
            self.tagger_2_demage = 1
        elif tagger_2 == 2:
            self.tagger_2_demage = 2
        elif tagger_2 == 3 or tagger_2 == 0:
            self.tagger_2_demage = 4

        if self.game_mode==1:
            # Aiming mode: turn off both targets, then light one random target
            # and arm only its IR receiver
            for i in range(2):
                LED_TARG[i].value(0)
            random_idx= urandom.randint(0,1)
            RECV_RX[random_idx]= NEC_8(RECV[random_idx], callback=ir_recv)
            LED_TARG[random_idx].value(1)

        if self.game_mode!=1:
            # Health / Showdown: arm both vest receivers, light both targets,
            # then fill the health bar one LED at a time as a start sequence
            ir_rx1 = NEC_8(IR_RECV1, callback=ir_recv_1)
            ir_rx2 = NEC_8(IR_RECV2, callback=ir_recv_2)
            LED_TARG[0].value(1)
            LED_TARG[1].value(1)
            for i in range(4):
                LED_HEALTH[i].value(0)
            for i in range(4):
                LED_HEALTH[i].value(1)
                time.sleep(0.75)

        self.player_1.set_params(self.tagger_1, self)
        print(f"Game Mode: {self.game_mode}")
        print(f"Tagger 1: {self.tagger_1}")
        print(f"Tagger 2 demage: {self.tagger_2_demage}")
        print(f"Fire Rate 1: {self.TRIGGER_HOLD_INTERVAL}")
        print(f"Round: {self.rnd}")
        self.print_status()

    def print_status(self):
        # Debug output over the serial console
        print("==========================")
        print(f"Round {self.curr_round} / {self.rnd}")
        print(f"\nPlayer 1:")
        print(f"hp: {self.player_1.hp} | tg: {self.player_1.tg} | cl: {self.player_1.cl}")
        print("==========================")

    def send_player_status_update(self):
        # [3] Player status: "3 <hp> <cells>"
        e.send(peer, f"3 {self.player_1.hp} {self.player_1.cl} ", True)

    def handle_ir_hit(self):
        global RECV_RX
        # Aiming mode: score the hit and move the target to a random position
        if self.game_mode==1:
            for i in range(2):
                LED_TARG[i].value(0)
            random_idx= urandom.randint(0,1)
            RECV_RX[random_idx]= NEC_8(RECV[random_idx], callback=ir_recv)
            LED_TARG[random_idx].value(1)
            self.player_1.hp += 1

        # Health / Showdown: lose HP and update the health bar LEDs
        if self.game_mode!=1:
            self.player_1.hp -= self.tagger_2_demage
            hp = self.player_1.hp
            if hp == 3:
                LED_HEALTH[3].value(0)
            elif hp ==2:
                LED_HEALTH[3].value(0)
                LED_HEALTH[2].value(0)
            elif hp ==1:
                LED_HEALTH[3].value(0)
                LED_HEALTH[2].value(0)
                LED_HEALTH[1].value(0)
            elif hp ==0:
                LED_HEALTH[3].value(0)
                LED_HEALTH[2].value(0)
                LED_HEALTH[1].value(0)
                LED_HEALTH[0].value(0)

        self.send_player_status_update()

    def handle_reload_btn(self):
        # Reload is only allowed in Health mode. Refill cells, then block for
        # the preset's reload time before reporting the new status.
        if self.game_mode == 0:
            self.player_1.cl = self.player_1.rl
            self.display_num()
            time.sleep_ms(self.RELOAD_INTERVAL)
            self.send_player_status_update()

    def handle_end_btn(self):
        # [1] Game conclusion request; the control unit broadcasts the end
        e.send(peer, "1 ", True)

    def handle_game_conclusion(self):
        self.game_conclusion = True

    def handle_round_start(self, new_rnd):
        # Reset HP and cells for the new round
        self.round_end = False
        self.player_1.hp = 4
        self.player_1.cl = self.player_1.rl
        self.curr_round = new_rnd
        self.display_num()
        self.print_status()

        # Countdown pause before every round after the first
        if self.curr_round > 1:
            time.sleep(5)

    def handle_round_end(self, end_rnd):
        self.round_end = True

    def run(self):
        # Main loop: poll the trigger (active low) and fire while it is held,
        # at most once every TRIGGER_HOLD_INTERVAL ms
        while True:
            if self.game_conclusion:
                break

            # Showdown mode: unlimited cells
            if self.game_mode == 2:
                if trigger.value() == 0:
                    ir_tx.transmit(1, 2)    # NEC frame: address 1, command 2
                    self.display_num()
                    self.send_player_status_update()
                    print(f"Cell: Unlimited -- Showdown Mode")
                    time.sleep_ms(self.TRIGGER_HOLD_INTERVAL)

            # Health mode: each shot uses one cell.
            # (In Aiming mode Tagger 2 is the target board and does not fire.)
            elif self.game_mode == 0:
                if trigger.value() == 0 and self.player_1.cl > 0:
                    self.player_1.cl -= 1
                    ir_tx.transmit(1, 2)
                    self.display_num()
                    self.send_player_status_update()
                    print(f"Cell: {self.player_1.cl}")
                    time.sleep_ms(self.TRIGGER_HOLD_INTERVAL)


    def display_num(self):
        # Show the remaining cells on the 7-segment display
        round_num= self.curr_round
        cell_num= self.player_1.cl
        disp7S(pin1,pin2,pin3,pin4,pin5,pin6,pin7,f'{cell_num:2d}  ')



# Buttons are active low (internal pull-up). The trigger is polled in
# GameLogic.run(); Reload and End use falling-edge interrupts.
trigger = Pin(TRIGGER_PIN, Pin.IN, Pin.PULL_UP)
reload_btn = Pin(RELOAD_PIN, Pin.IN, Pin.PULL_UP)
reload_btn.irq(trigger=Pin.IRQ_FALLING, handler=reload_pressed_handler)
end_btn = Pin(END_PIN, Pin.IN, Pin.PULL_UP)
end_btn.irq(trigger=Pin.IRQ_FALLING, handler=end_pressed_handler)

game_logic = GameLogic()
e.irq(esp_recv)


# Run one game at a time; after the game ends, start fresh and wait for the
# next [0] Initialization from the control unit
while True:
    game_logic.run()
    game_logic = GameLogic()
