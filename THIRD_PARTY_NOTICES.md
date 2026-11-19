# Third-Party Notices

This project includes code written by people outside the Laser Dual team. Each
file below keeps its original copyright header, and a short note at the top of
the file links back to its source.

| Files in this repo | Source | Version | Changes |
|---|---|---|---|
| `firmware/lib/ir_rx/__init__.py` | [peterhinch/micropython_ir](https://github.com/peterhinch/micropython_ir) `ir_rx/__init__.py` | commit `25a9727` (2024-02-12) | None |
| `firmware/lib/ir_rx/nec.py` | [peterhinch/micropython_ir](https://github.com/peterhinch/micropython_ir) `ir_rx/nec.py` | commit `25a9727` | One line: the receiver pin is passed to the callback instead of `0` (marked `# Laser Dual: was 0`) |
| `firmware/lib/ir_tx/__init__.py` | [peterhinch/micropython_ir](https://github.com/peterhinch/micropython_ir) `ir_tx/__init__.py` | commit `25a9727` | None |
| `firmware/lib/ir_tx/nec.py` | [peterhinch/micropython_ir](https://github.com/peterhinch/micropython_ir) `ir_tx/nec.py` | commit `25a9727` | None |
| `firmware/lib/lcd_api.py` | [dhylands/python_lcd](https://github.com/dhylands/python_lcd) `lcd/lcd_api.py` | commit `7affb0b` | None |
| `firmware/lib/i2c_lcd.py` | [dhylands/python_lcd](https://github.com/dhylands/python_lcd) `lcd/machine_i2c_lcd.py` | commit `7affb0b` | Renamed to match the import in `control_unit.py`; content unchanged |

The pinned commits are the upstream versions that were current while the
project was built (spring 2024).

---

## micropython_ir

```
MIT License

Copyright (c) 2020 Peter Hinch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## python_lcd

```
The MIT License (MIT)

Copyright (c) 2013 Dave Hylands

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
