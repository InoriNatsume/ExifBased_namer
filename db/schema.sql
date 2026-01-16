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
  tags_json TEXT,
  tags_pos_json TEXT,
  tags_neg_json TEXT,
  tags_char_json TEXT
);

CREATE TABLE IF NOT EXISTS tags (
  image_id INTEGER NOT NULL,
  tag TEXT NOT NULL,
  source_type TEXT,
  source_idx INTEGER,
  FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image_payloads (
  image_id INTEGER NOT NULL,
  payload_index INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS presets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  variable_name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_tags_tag_source ON tags(tag, source_type);
CREATE INDEX IF NOT EXISTS idx_tags_image_id ON tags(image_id);
CREATE INDEX IF NOT EXISTS idx_payloads_image_id ON image_payloads(image_id);
CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name);
CREATE INDEX IF NOT EXISTS idx_presets_name ON presets(name);
CREATE INDEX IF NOT EXISTS idx_matches_variable ON matches(variable);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);

INSERT OR IGNORE INTO meta(schema_version) VALUES (2);
