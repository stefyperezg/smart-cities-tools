

def get_metadata ():
  return {
  "version": "1.0",
  "time_zone": "America/Guayaquil",
  "last_updated": None,
  "currency": "USD",
  "author": "City of Ambato",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "data": {}
}


def row_to_nested_dict(row):
    result = {}
    for col, val in row.items():
        parts = col.split(".")
        current = result
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = val
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
    return result