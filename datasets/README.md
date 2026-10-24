## Train Data Insert Script

**Script:** `database/sql/train_schema.sql`

This script populates the `TrainLine`, `TrainStation` and `StationLine` tables. It was generated from two LTA DataMall static datasets stored in `datasets/`:

| Source file | Used for |
|---|---|
| `Train-Station-Codes-and-Chinese-Names.xls` | Station codes, English and Chinese station names, and each station's line (English and Chinese line names) |
| `Train-Line-Codes-2.xlsx` | Line codes (e.g. CCL, DTL, EWL, NEL, NSL, TEL, BP, PG, SK), used to set `line_code` values |

### How the data was derived

- Each row in the station file became one `TrainStation` row (213 rows).
- Each station was linked to its line in `StationLine` (213 rows) using the prefix of its station code.
- `TrainLine` (11 rows) was built from the distinct lines in the station file. Chinese line names came from that file too.
- Station-code prefixes were mapped to line codes (e.g. `CC` -> `CCL`, `PE`/`PW`/`PTC` -> `PG`, `SE`/`SW`/`STC` -> `SK`).

### Data cleaning applied

- Spaces between characters in some Chinese station names were removed (stations NS12, EW30, EW32, TE1, TE2, TE3).
- Circle Line Extension (`CE`) and Changi Airport Branch Line (`CG`) are kept as separate lines, as in the station file.

### How to run

1. Run `create_database.sql` to create the database.
2. Run `train_schema.sql` as is. It creates the tables and inserts the data in the correct order, so no other scripts are needed.
3. Run the script as UTF-8 so the Chinese characters load correctly.