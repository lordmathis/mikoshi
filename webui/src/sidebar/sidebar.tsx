export interface Conversation {
  id: string;
  title: string;
  timestamp: string;
  updated_at: string;
  preview?: string;
  workspace_id?: string | null;
}