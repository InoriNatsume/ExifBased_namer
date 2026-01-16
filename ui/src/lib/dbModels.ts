export type TemplateInfo = {
  id: number;
  name: string;
  updated_at?: string | null;
};

export type PresetInfo = {
  id: number;
  name: string;
  source_kind: string;
  variable_name: string;
  updated_at?: string | null;
};
