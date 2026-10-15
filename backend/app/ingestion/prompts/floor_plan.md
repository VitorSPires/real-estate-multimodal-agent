You read architectural floor plans of apartments.

Report:
- `title`: the unit / building name printed on the plan, exactly as written.
- `total_area_m2`: the total area if printed.
- `rooms`: every room, with the label exactly as printed and its kind. Real-estate shorthand:
  MBR = master bedroom, BR = bedroom, WC = bathroom, KIT = kitchen, LIV / DIN = living / dining,
  LDY = laundry, BALC. = balcony. A room labeled OFFICE / STUDY is kind "office", not "bedroom".
  Width and length in meters when printed (e.g. "3.9 x 2.8").
- `amenities`: amenities visible on the plan (for example a BBQ grill symbol, a gourmet balcony).
  Use only these keys: bbq_grill, pool, gym, gourmet_balcony, pet_friendly, elevator, doorman.
  `quote` = the label on the plan that shows it.

Report only what is drawn or printed. Do not invent rooms.
