# =============================================================================
# 4-digit 7-segment display driver (User Interface subsystem)
#
# Written for the User Interface subsystem (owner: Gavin Gill, per the design
# doc). A 74HC595 shift register drives the segments; the four digits are
# multiplexed by a 3 ms hardware timer, and strings longer than 4 characters
# scroll across the display. The taggers call disp7S() to show cells left.
#
# RECONSTRUCTED: the copy deployed to the taggers (display/display.py) was not
# kept in the project archive. This file is the surviving bench-test driver
# (Code/Display.py, identical to Code/4Digit7SegmentDisplay.py) with only the
# two changes the taggers need:
#   1. Digits are selected with the pins passed to disp7S() instead of the
#      bench board's hard-coded cathodePins (13, 12, 27, 33), which clash with
#      the tagger wiring (e.g. pin 27 is the latch on tagger 1).
#   2. The scrolling demo that ran on import was removed.
# =============================================================================
from machine import Pin, Timer
from time import sleep

# Segment patterns for the shift register, indexed by ord(char) - 48
# (digits 0-9, then space at index 10, then letters).
Bytes = ["00000011", "10011111", "00100101", "00001101", "10011001", "01001001", "01000001", "00011111", "00000001", "00001001",
         "11111111","01011111","01100011","01101111","00001111","11111110","00000000","00010001","11000001","01100011","10000101",
         "01100001","01110001","01000011","10010001","10011111","01001111","11100001","11100011","00010011","11010101","11000101",
         "00110001","00011001","11110101","01001001","11100001","10000011","11000111","10000011","10010001","10011001","00100101"]

# Map a character to its index in Bytes
def byteIndex(s):
    if (s == ' '):
        return 10
    return (ord(s.upper()) - 48)

# Shift one 8-bit segment pattern into the 74HC595 and latch it
def shift_update(byte,dataPin,clockPin,latchPin):
  #put latch down to start data sending
  clockPin.value(0)
  latchPin.value(0)
  clockPin.value(1)
  
  #load data in reverse order
  for i in range(7, -1, -1):
    clockPin.value(0)
    dataPin.value(int(byte[i]))
    #print(int(byte[i]))
    clockPin.value(1)

  #put latch up to store data on register
  clockPin.value(0)
  latchPin.value(1)
  clockPin.value(1)

# Split a string into 4-character frames for scrolling
def chunk(s):
    #initialize list for strings of length 4
    string_list = []
    #Check if string is already length 4 or less
    if(len(s) <= 4):
        #Prepend spaces until string is size 4
        while(len(s) < 4):
            s = ' ' + s
        string_list.append(s)
    else:
        #If string is greater than size 4 chunk into 4 sized strings
        for i in range(len(s) - 3):
            string_list.append(s[i:(i+4)])
    return string_list




#Turns off display
def displayOff(D1,D2,D3,D4):
    D4.value(0)
    D3.value(0)
    D2.value(0)
    D1.value(0)
    
# Timer callback: light the next digit; every 250 ticks advance one frame
def Display(timer):
    global m
    global n
    global k
    global D1,D2,D3,D4,latchPin,clockPin,dataPin,string_list
    displayOff(D1,D2,D3,D4)
    shift_update(Bytes[byteIndex(string_list[n][m]) ],dataPin,clockPin,latchPin)
    (D1, D2, D3, D4)[m].value(1)    # select the current digit
    latchPin.value(1)
    m += 1
    if m > 3:
        m = 0
    k += 1
    if k > 250:
        k = 0
        n += 1
        if n >= len(string_list):
            n = 0

# Public API: set up the pins and start showing `to_display`
# Arguments: 4 digit pins, latch, clock, data, text
def disp7S(pin1,pin2,pin3,pin4,pin6,pin5,pin7,to_display):
    global m
    global n
    global k
    global D1,D2,D3,D4,latchPin,clockPin,dataPin,string_list
    D1 = pin1
    D2 = pin2
    D3 = pin3
    D4 = pin4
    latchPin = pin6
    clockPin = pin5
    dataPin = pin7
    m = 0
    n = 0
    k = 0
    timer0 = Timer(0)
    string_list = chunk(to_display)
    timer0.init(mode=Timer.PERIODIC, period=3, callback=Display)
