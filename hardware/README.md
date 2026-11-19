# Hardware

Both boards were designed in EasyEDA by Jonathan Kao. They are 2-layer PCBs
built around the ESP32-WROOM-32E module. The fabrication files (Gerbers, BOMs
and pick-and-place) are EasyEDA exports with LCSC part numbers, kept as
exported.

| Board | Schematic | Layout | Preview |
|---|---|---|---|
| Control unit | [schematic.pdf](control-unit/schematic.pdf) | [pcb.pdf](control-unit/pcb.pdf), [pcb-layers.pdf](control-unit/pcb-layers.pdf) | [3D render](control-unit/pcb-3d.png) |
| Tagger | [schematic.pdf](tagger/schematic.pdf) | [pcb.pdf](tagger/pcb.pdf), [pcb-layers.pdf](tagger/pcb-layers.pdf) | [3D render](tagger/pcb-3d.png), [photo of the fabricated board](tagger/pcb-photo.jpg) |

## Files per board

- `gerber/`: the Gerber and drill files, unzipped so they can be browsed here.
- `fabrication/full-assembly/`: the files to order an assembled board. The
  Gerber zip has the same contents as `gerber/`; the BOM and pick-and-place
  (CPL) files list every part.
- `fabrication/without-esp32-buttons-connectors/` (control unit only): the same
  Gerbers with a reduced BOM and CPL that leave the ESP32 module, the four menu
  buttons, the J1/J2 pin headers and the LCD connector off the factory assembly.
- `control-unit/fabrication/full-assembly/bom_with_number.csv`: the full control
  unit BOM with LCSC unit prices and order quantities.

Some BOM and CPL files are UTF-16, tab-separated text, as EasyEDA exports them,
so GitHub may not preview them. Open them in a spreadsheet program.

## Firmware pin mapping

The firmware in [`firmware/`](../firmware) uses the pin numbers of hand-wired
bench setups, not these boards, so it would need its pin constants updated to
run on them. See [Known limitations](../README.md#known-limitations).
