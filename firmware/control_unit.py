# =============================================================================
# Laser Dual - Control Unit firmware (MicroPython, ESP32)
#
# Responsibilities:
#   1. Game setup UI: walk the player through mode / tagger / round selection
#      on a 16x2 I2C LCD using four push buttons (Left, Right, Select, Back).
#   2. Game coordinator: broadcast game parameters to both taggers over
#      ESP-NOW, track each player's status, decide when a round / the game
#      ends, and show scores on the LCD.
#
# Message protocol: see docs/esp-now-message-format.pdf
#   0 Initialization      CU -> taggers   "0 <mode> <tag1> <tag2> <rounds>"
#   1 Game conclusion     CU <-> taggers  "1"
#   3 Player status       taggers -> CU   "3 <hp> <cells>"
#   4 Round start         CU -> taggers   "4 <round>"
#   5 Round end           CU -> taggers   "5 <round>"
#
# Game modes:     0 = Health, 1 = Aiming, 2 = Showdown
# Tagger presets: 1 = SWIFT, 2 = PULSE, 3 = NOVA (0 = not selected)
# =============================================================================

import machine
from machine import Pin, SoftI2C
import network
import espnow
import time

# ========================== Third-party code ==========================
# 'lcd_api.py', 'i2c_lcd.py' in firmware/lib/ (code unmodified; i2c_lcd.py is
# upstream lcd/machine_i2c_lcd.py, renamed)
# Author: Dave Hylands
# Repository: https://github.com/dhylands/python_lcd
# License: The MIT License (MIT)
#     Copyright (c) 2013 Dave Hylands
#
#     Permission is hereby granted, free of charge, to any person obtaining a copy of
#     this software and associated documentation files (the "Software"), to deal in
#     the Software without restriction, including without limitation the rights to
#     use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
#     the Software, and to permit persons to whom the Software is furnished to do so,
#     subject to the following conditions:
#
#     The above copyright notice and this permission notice shall be included in all
#     copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#     IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
#     FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#     COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
#     IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
#     CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# Accessed on: 2024-02-09
# ======================================================================

from lcd_api import LcdApi
from i2c_lcd import I2cLcd

# ---------------------------------------------------------------------------
# ESP-NOW setup
# ESP-NOW needs the Wi-Fi station interface active but not connected to an AP.
# ---------------------------------------------------------------------------
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()

espnow = espnow.ESPNow()
espnow.active(True)

# Peers must be registered before send(). Use firmware/tools/print_mac_addr.py
# to read each board's MAC address.
peer1 = b'\xc4\xdd\x57\xc9\x84\xbc'   # Tagger 1 (Player 1) MAC address
espnow.add_peer(peer1)

peer2 = b'\x60\x01\x94\x5a\x9c\xf0'   # Tagger 2 (Player 2) MAC address
espnow.add_peer(peer2)

# ---------------------------------------------------------------------------
# Peripherals
# ---------------------------------------------------------------------------
# 16x2 character LCD behind a PCF8574 I2C backpack (address 0x27)
i2c = SoftI2C(scl=Pin(9), sda=Pin(8), freq=100000)
lcd = I2cLcd(i2c, 0x27, 2, 16)

# Navigation buttons: active low (internal pull-up, pressed = 0).
# 'start' is configured but the menu loop below never acts on it.
buttons = {
    'left': Pin(12, Pin.IN, Pin.PULL_UP),
    'right': Pin(6, Pin.IN, Pin.PULL_UP),
    'select': Pin(10, Pin.IN, Pin.PULL_UP),
    'back': Pin(11, Pin.IN, Pin.PULL_UP),
    'start': Pin(7, Pin.IN, Pin.PULL_UP)
}

# ---------------------------------------------------------------------------
# LCD page content (each entry is exactly 16 characters = one LCD row)
# ---------------------------------------------------------------------------
modes = ["<    HEALTH    >", "<    AIMING    >", "<   SHOWDOWN   >"]
modes_2 = ["HEALTH", "AIMING", "SHOWDOWN"]
# Tagger presets. Columns: name, HP damage dealt, reload time (s), cells (shots)
taggers = ["<SWIFT  1  1 15>", "<PULSE  2  2  8>", "<NOVA   4  4  2>"]
rounds = [
    "<      01      >", "<      02      >", "<      03      >",
    "<      04      >", "<      05      >", "<      06      >",
    "<      07      >", "<      08      >", "<      09      >",
    "<      10      >"
]


class GameSetUp:
    # Game parameter selection flow, driven by `page_stage`:
    #   0 Cover -> 1 Game mode -> 2 Tagger 1 -> 3 Tagger 2 -> 4 Rounds -> 5 Done
    # Pages that do not apply to a mode are skipped:
    #   Health:   0 -> 1 -> 2 -> 3 -> 4
    #   Aiming:   0 -> 1 -> 2 ------> 4   (single player, no Tagger 2)
    #   Showdown: 0 -> 1 -----------> 4   (fixed tagger behavior)
    def __init__(self):
        # Selection state
        self.page_stage = 0
        self.select_idx = 0     # Highlighted option on the current page
        self.game_mode = 0
        self.tagger_1 = 0
        self.tagger_2 = 0
        self.rnd = 0

        # Show the cover page
        self.show_page(0)

    def show_cover_page(self):
        lcd.move_to(0, 0)
        lcd.putstr("Laser Dual      ")
        lcd.move_to(0, 1)
        lcd.putstr("  Click Select  ")

    def show_mode_page(self):
        self.select_idx = 0
        lcd.move_to(0, 0)
        lcd.putstr("Game Mode       ")
        lcd.move_to(0, 1)
        lcd.putstr(modes[0])

    def update_mode_page(self, shift):
        # Cycle through the options; only the second row is redrawn
        self.select_idx = (self.select_idx + shift) % 3
        lcd.move_to(0, 1)
        lcd.putstr(modes[self.select_idx])

    def show_tagger_page(self, tag_id):
        self.select_idx = 0
        lcd.move_to(0, 0)
        lcd.putstr("Tag-{}  HP RL NC ".format(tag_id))
        lcd.move_to(0, 1)
        lcd.putstr(taggers[0])

    def update_tagger_page(self, shift):
        self.select_idx = (self.select_idx + shift) % 3
        lcd.move_to(0, 1)
        lcd.putstr(taggers[self.select_idx])

    def show_round_page(self):
        self.select_idx = 0
        lcd.move_to(0, 0)
        lcd.putstr("Round           ")
        lcd.move_to(0, 1)
        lcd.putstr(rounds[0])

    def update_round_page(self, shift):
        self.select_idx = (self.select_idx + shift) % 10
        lcd.move_to(0, 1)
        lcd.putstr(rounds[self.select_idx])

    def show_selection_complete_page(self):
        lcd.move_to(0, 0)
        lcd.putstr("MODE T1 T2 ROUND")
        lcd.move_to(0, 1)
        lcd.putstr(f"   {self.game_mode}  {self.tagger_1}  {self.tagger_2}    {self.rnd:2}")

    def show_page(self, page_stage):
        self.page_stage = page_stage
        if page_stage == 0:
            self.show_cover_page()
        elif page_stage == 1:
            self.show_mode_page()
        elif page_stage == 2:
            self.show_tagger_page(1)
        elif page_stage == 3:
            self.show_tagger_page(2)
        elif page_stage == 4:
            self.show_round_page()

    def update_page(self, shift):
        # Left / right buttons: move the selection on the current page
        if self.page_stage == 1:
            self.update_mode_page(shift)
        elif self.page_stage == 2 or self.page_stage == 3:
            self.update_tagger_page(shift)
        elif self.page_stage == 4:
            self.update_round_page(shift)

    def run(self):
        # Poll the buttons until every parameter has been selected (stage 5)
        while True:
            for button_name, button_pin in buttons.items():
                if not button_pin.value():  # Active low: 0 means pressed
                    if button_name == 'select':
                        # Confirm the current option and advance to the next page
                        if self.page_stage == 0:
                            self.page_stage = 1
                            self.show_mode_page()
                            print('here')

                        elif self.page_stage == 1:
                            self.game_mode = self.select_idx
                            if self.game_mode == 2:     # Showdown: skip tagger pages
                                self.page_stage += 3
                            else:
                                self.page_stage += 1

                        elif self.page_stage == 2:
                            # Tagger presets are 1-based (0 = not selected)
                            self.tagger_1 = self.select_idx + 1
                            if self.game_mode == 0:     # Health: also pick Tagger 2
                                self.page_stage += 1
                            else:                       # Aiming: skip Tagger 2
                                self.page_stage += 2

                        elif self.page_stage == 3:
                            self.tagger_2 = self.select_idx + 1
                            self.page_stage += 1

                        elif self.page_stage == 4:
                            self.rnd = self.select_idx + 1
                            self.page_stage += 1

                        if self.page_stage == 5:
                            self.show_selection_complete_page()
                            break
                        else:
                            self.select_idx = 0
                            self.show_page(self.page_stage)

                    elif button_name == 'left':
                        self.update_page(-1)

                    elif button_name == 'right':
                        self.update_page(1)

                    elif button_name == 'back':
                        # Clear the current choice and return to the previous
                        # page, mirroring the page skips used for each mode
                        if self.page_stage == 1:
                            self.game_mode = 0
                            self.page_stage = 0

                        elif self.page_stage == 2:
                            self.tagger_1 = 0
                            self.page_stage = 1

                        elif self.page_stage == 3:
                            self.tagger_2 = 0
                            self.page_stage = 2

                        elif self.page_stage == 4:
                            self.rnd = 0
                            if self.game_mode == 0:
                                self.page_stage = 3
                            elif self.game_mode == 1:
                                self.page_stage = 2
                            elif self.game_mode == 2:
                                self.page_stage = 1

                        self.select_idx = 0
                        self.show_page(self.page_stage)

            if self.page_stage == 5:
                break
            else:
                pass

            time.sleep(0.15)  # Poll interval; also acts as a simple button debounce


class GameLogic:
    # Runs one full game: sends the parameters to the taggers, reacts to
    # player status updates received over ESP-NOW, and decides when each
    # round and the whole game end.
    def __init__(self, game_mode, tagger_1, tagger_2, rnd):

        self.game_conclusion = False    # Set when the game is over; ends run()
        self.game_mode = game_mode
        self.tagger_1 = tagger_1
        self.tagger_2 = tagger_2
        self.rnd = rnd                  # Total number of rounds

        self.init_acks = [False, False]
        self.curr_round = 1

        class Player():
            # Control unit's mirror of a player's state.
            # hp: health bar (0-4), cl: cells (shots) left, score: rounds won
            # (in Aiming mode, score is the number of targets hit)
            def __init__(self, tagger_id):
                self.tg = tagger_id
                self.hp = 4
                self.score = 0
                self.cl = -1
                if self.tg == 1:        # SWIFT
                    self.cl = 15
                elif self.tg == 2:      # PULSE
                    self.cl = 8
                elif self.tg == 3:      # NOVA
                    self.cl = 2

        self.player_1 = Player(self.tagger_1)
        self.player_2 = Player(self.tagger_2)
        print(f"Game Mode: {self.game_mode}")
        print(f"Tagger 1: {self.tagger_1}")
        print(f"Tagger 2: {self.tagger_2}")
        print(f"Round: {self.rnd}")
        self.print_status()
        self.send_initialization()

    def print_status(self):
        # Debug output over the serial console
        print("==========================")
        print(f"Round {self.curr_round} / {self.rnd}")
        print(f"\nPlayer 1:")
        print(f"Score: {self.player_1.score}")
        print(f"hp: {self.player_1.hp} | tg: {self.player_1.tg} | cl: {self.player_1.cl}")
        print(f"\nPlayer 2:")
        print(f"Score: {self.player_2.score}")
        print(f"hp: {self.player_2.hp} | tg: {self.player_2.tg} | cl: {self.player_2.cl}")
        print("==========================")

    # ------------------------------------------------------------------
    # LCD pages
    # ------------------------------------------------------------------
    def show_retrying_page(self):
        lcd.move_to(0, 0)
        lcd.putstr("Retrying...     ")
        lcd.move_to(0, 1)
        lcd.putstr("                ")

    def show_init_error_page(self):
        # Shown when the taggers do not acknowledge initialization.
        # Blocks until the player presses Select to retry.
        lcd.move_to(0, 0)
        lcd.putstr("Click Select to ")
        lcd.move_to(0, 1)
        lcd.putstr("Retry Connection")
        while True:
            if not buttons['select'].value():
                self.show_retrying_page()
                break
            time.sleep(0.05)

    def show_player_status_page(self):
        # Row 1: game mode and round progress; row 2: scores
        lcd.move_to(0, 0)
        if self.rnd == 10:
            lcd.putstr(f"{modes_2[self.game_mode]:<8}   {self.curr_round:2}/{self.rnd:2}")
        else:
            lcd.putstr(f"{modes_2[self.game_mode]:<8}    {self.curr_round:2}/{self.rnd:1}")
        lcd.move_to(0, 1)
        if self.game_mode == 1:
            # Aiming mode is single player
            lcd.putstr(f"P1: {self.player_1.score:3}         ")
        else:
            lcd.putstr(f"P1: {self.player_1.score:2}    P2: {self.player_2.score:2}")

    def show_conclusion_page(self):
        lcd.move_to(0, 0)

        if self.game_mode == 1:
            # Aiming mode: show the player's score with the tagger used
            lcd.putstr("Your Score      ")
            lcd.move_to(0, 1)
            if self.player_1.tg == 1:
                lcd.putstr(f"Swift        {self.player_1.score:3}")
            elif self.player_1.tg == 2:
                lcd.putstr(f"Pulse        {self.player_1.score:3}")
            elif self.player_1.tg == 3:
                lcd.putstr(f"Nova         {self.player_1.score:3}")
        else:
            # Two-player modes: "Winner" is placed above the winning player
            if self.player_1.score > self.player_2.score:
                lcd.putstr("Winner          ")
                lcd.move_to(0, 1)
                lcd.putstr(f"P1: {self.player_1.score:2}    P2: {self.player_2.score:2}")
            elif self.player_1.score < self.player_2.score:
                lcd.putstr("          Winner")
                lcd.move_to(0, 1)
                lcd.putstr(f"P1: {self.player_1.score:2}    P2: {self.player_2.score:2}")
            else:
                lcd.putstr("      Draw      ")
                lcd.move_to(0, 1)
                lcd.putstr(f"P1: {self.player_1.score:2}    P2: {self.player_2.score:2}")

    # ------------------------------------------------------------------
    # Outgoing ESP-NOW messages
    # ------------------------------------------------------------------
    def send_initialization(self):
        # [0] Initialization: send the selected parameters to both taggers.
        # espnow.send(..., sync=True) returns True once the peer ACKs at the
        # MAC layer. After more than 5 failed attempts, ask the player to retry.
        ack1 = False
        ack2 = True
        retry = 0
        while not ack1 or not ack2:
            if retry > 5:
                retry = 0
                self.show_init_error_page()
                print("==========================\nRetrying...\n")
            ack1 = espnow.send(peer1, f"0 {self.game_mode} {self.tagger_1} {self.tagger_2} {self.rnd} ", True)
            ack2 = espnow.send(peer2, f"0 {self.game_mode} {self.tagger_1} {self.tagger_2} {self.rnd} ", True)
            # NOTE: ACK results are overridden, so the game starts even when a
            # tagger is offline (most likely left in from single-tagger testing).
            ack2 = True
            ack1 = True
            print(f"Initialization Sent {retry}")
            print(f"Tagger 1: {ack1}, Tagger 2: {ack2}")
            time.sleep(0.5)
            retry += 1

        self.send_round_start()
        self.show_player_status_page()

    def send_round_start(self):
        # [4] Round start: taggers reset HP and cells for the new round
        espnow.send(peer1, f"4 {self.curr_round}", True)
        espnow.send(peer2, f"4 {self.curr_round}", True)
        print(f"Round Start {self.curr_round} Sent")

    def send_round_end(self):
        # [5] Round end
        espnow.send(peer1, f"5 {self.curr_round}", True)
        espnow.send(peer2, f"5 {self.curr_round}", True)
        print(f"Round End {self.curr_round} Sent")

    def send_game_conclusion(self):
        # [1] Game conclusion: taggers stop and wait for the next game
        espnow.send(peer1, f"1", True)
        espnow.send(peer2, f"1", True)
        print(f"Game Conclusion Sent")

    # ------------------------------------------------------------------
    # Game state handling
    # ------------------------------------------------------------------
    def check_round_end(self):
        # Decide whether the current round is over after a status update
        round_is_end = False

        # Aiming mode: the round ends when the player runs out of cells
        if self.game_mode == 1:
            if self.player_1.cl == 0:
                round_is_end = True

        # Health and Showdown modes: the round ends when a player's HP hits 0,
        # and the opponent wins the round
        else:
            if self.player_1.hp == 0:
                self.player_2.score += 1
                round_is_end = True
            elif self.player_2.hp == 0:
                self.player_1.score += 1
                round_is_end = True

        self.show_player_status_page()

        if round_is_end is True:
            self.send_round_end()
            self.curr_round += 1
            print(self.curr_round, self.rnd)
            if self.curr_round > self.rnd:
                self.handle_game_conclusion()
            else:
                self.send_round_start()

    def handle_player_status_update(self, host, data):
        # [3] Player status: "3 <hp> <cells>". The sender is identified by MAC.
        if self.game_mode == 1:
            # Aiming mode: Tagger 1 is the shooter (reports cells left) and
            # Tagger 2 is the target board (its "hp" field carries the hit count)
            if host == peer1:
                self.player_1.cl = int(data[2])
            elif host == peer2:
                self.player_1.score = int(data[1])
        else:
            if host == peer1:
                self.player_1.hp = int(data[1])
                self.player_1.cl = int(data[2])
            elif host == peer2:
                self.player_2.hp = int(data[1])
                self.player_2.cl = int(data[2])

        self.check_round_end()

    def handle_game_conclusion(self):
        # Notify the taggers, show the result, and wait for Select to start
        # a new game
        self.send_game_conclusion()
        self.show_conclusion_page()
        while True:
            if not buttons['select'].value():
                self.game_conclusion = True
                break
            time.sleep(0.05)

    def lcd_off(self):
        lcd.display_off()

    def espnow_receive(self, e):
        # ESP-NOW receive callback: parse "<type> <args...>" and dispatch
        host, msg_encoded = e.recv()
        if msg_encoded:
            msg = msg_encoded.decode()
            data = msg.split()
            print(msg)
            if data:
                if data[0] == '3':
                    self.handle_player_status_update(host, data)
                elif data[0] == '1':
                    # A player pressed the End button on a tagger
                    self.handle_game_conclusion()


    def run(self):
        # Messages are handled in the ESP-NOW callback, so the main loop only
        # waits for the game to finish (no threading needed)
        espnow.irq(self.espnow_receive)
        while True:
            if self.game_conclusion:
                break
            time.sleep_ms(10)


# Main loop: parameter selection -> play one game -> repeat
while True:
    game_setup = GameSetUp()
    game_setup.run()
    game_logic = GameLogic(
        game_setup.game_mode,
        game_setup.tagger_1,
        game_setup.tagger_2,
        game_setup.rnd
    )
    game_logic.run()
