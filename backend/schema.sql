CREATE TABLE IF NOT EXISTS gics_version(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL,
  effective_date TEXT,
  source_url TEXT,
  checksum TEXT
);

CREATE TABLE IF NOT EXISTS gics_sector(
  code2 TEXT NOT NULL,
  name TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code2, version_id),
  FOREIGN KEY(version_id) REFERENCES gics_version(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gics_group(
  code4 TEXT NOT NULL,
  name TEXT NOT NULL,
  sector_code2 TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code4, version_id),
  FOREIGN KEY(sector_code2, version_id) REFERENCES gics_sector(code2, version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gics_industry(
  code6 TEXT NOT NULL,
  name TEXT NOT NULL,
  group_code4 TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code6, version_id),
  FOREIGN KEY(group_code4, version_id) REFERENCES gics_group(code4, version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gics_sub_industry(
  code8 TEXT NOT NULL,
  name TEXT NOT NULL,
  definition TEXT,
  industry_code6 TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code8, version_id),
  FOREIGN KEY(industry_code6, version_id) REFERENCES gics_industry(code6, version_id) ON DELETE CASCADE
);
