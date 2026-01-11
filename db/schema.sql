-- SQLite schema (initial draft)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
  schema_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  mtime INTEGER NOT NULL,
  size INTEGER NOT NULL,
  hash TEXT,
  tags_json TEXT
);

CREATE TABLE IF NOT EXISTS tags (
  image_id INTEGER NOT NULL,
  tag TEXT NOT NULL,
  FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matches (
  image_id INTEGER NOT NULL,
  variable TEXT NOT NULL,
  status TEXT NOT NULL,
  values_json TEXT,
  FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_images_path ON images(path);
CREATE INDEX IF NOT EXISTS idx_images_mtime ON images(mtime);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_matches_variable ON matches(variable);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);

INSERT OR IGNORE INTO meta(schema_version) VALUES (1);
