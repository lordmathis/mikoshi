export interface Conversation {
  id: string;
  title: string;
  timestamp: string;
  preview?: string;
  workspace_id?: string | null;
}