import { Send, Bot, Zap, Plus, Upload, Link as LinkIcon, Mic, Square, FileText, Slash, X } from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { ChatSettingsDialog, type ChatSettings } from "./chat-settings-dialog";
import { FileAttachments } from "./file-attachments";
import { getToolLabel, formatModelLabel } from "../lib/formatters";
import { useVoiceRecording } from "../hooks/use-voice-recording";
import { useMentionTrigger } from "../hooks/use-mention-trigger";
import { MentionDropdown } from "./mention-dropdown";
import { api, type Skill, type ConnectorEntry } from "../lib/api";

interface ChatInputProps {
  inputValue: string;
  isEditingMode?: boolean;
  onInputChange: (value: string) => void;
  onCancelEdit?: () => void;
  onSend: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  isSending: boolean;
  isUploadingFiles: boolean;
  currentConversationId: string | undefined;
  chatSettings: ChatSettings;
  onSettingsChange: (settings: ChatSettings) => void;
  uploadedFiles: import('../lib/api').FileResource[];
  connectorEntries: ConnectorEntry[];
  onRemoveFile: (fileId: string) => void;
  onRemoveConnectorEntry: (connectorId: string, resourceId: string) => void;
  onEditConnectorEntry: (connectorId: string, resourceId: string) => void;
  onFileUploadClick: () => void;
  onConnectorDialogOpen: () => void;
  onChatUpdated: () => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  workspaceFiles: string[];
  hasWorkspace: boolean;
}

export function ChatInput({
  inputValue,
  isEditingMode,
  onInputChange,
  onCancelEdit,
  onSend,
  onKeyDown,
  isSending,
  isUploadingFiles,
  currentConversationId,
  chatSettings,
  onSettingsChange,
  uploadedFiles,
  connectorEntries,
  onRemoveFile,
  onRemoveConnectorEntry,
  onEditConnectorEntry,
  onFileUploadClick,
  onConnectorDialogOpen,
  onChatUpdated,
  textareaRef,
  fileInputRef,
  onFileChange,
  workspaceFiles,
  hasWorkspace,
}: ChatInputProps) {
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      const newHeight = Math.min(textarea.scrollHeight, 300);
      textarea.style.height = `${newHeight}px`;
    }
  }, [inputValue, textareaRef]);

  const {
    isRecording,
    isProcessing,
    error: recordingError,
    startRecording,
    stopRecording,
    setProcessing,
    clearError,
  } = useVoiceRecording();

  const [skills, setSkills] = useState<Skill[]>([]);

  useEffect(() => {
    const loadSkills = async () => {
      try {
        const result = await api.listSkills();
        setSkills(result.skills);
      } catch (error) {
        console.error('Failed to load skills:', error);
      }
    };
    loadSkills();
  }, []);

  useEffect(() => {
    if (recordingError) {
      console.error('Voice recording error:', recordingError);
      setTimeout(clearError, 5000);
    }
  }, [recordingError, clearError]);

  const fileMention = useMentionTrigger<string>({
    trigger: "@",
    items: hasWorkspace ? workspaceFiles : [],
    searchFn: (filePath, query) =>
      filePath.toLowerCase().includes(query.toLowerCase()),
  });

  const skillMention = useMentionTrigger<Skill>({
    trigger: "/",
    items: skills,
    searchFn: (skill, query) =>
      skill.name.toLowerCase().includes(query.toLowerCase()),
  });

  const applyInsert = useCallback(
    (result: { text: string; cursorPos: number }) => {
      if (!result.text) return;
      onInputChange(result.text);
      setTimeout(() => {
        textareaRef.current?.focus();
        textareaRef.current?.setSelectionRange(result.cursorPos, result.cursorPos);
      }, 0);
    },
    [onInputChange, textareaRef]
  );

  const handleInputChangeWithMentions = useCallback(
    (value: string) => {
      onInputChange(value);

      const cursorPos = textareaRef.current?.selectionStart || 0;

      fileMention.handleInputChange(value, cursorPos);
      skillMention.handleInputChange(value, cursorPos);
    },
    [onInputChange, textareaRef, fileMention, skillMention]
  );

  const handleFileSelect = useCallback(
    (index: number) => {
      const item = fileMention.filteredItems[index];
      const result = fileMention.insert(item, (path) => `'${path}' `);
      applyInsert(result);
    },
    [fileMention, applyInsert]
  );

  const handleSkillSelect = useCallback(
    (index: number) => {
      const item = skillMention.filteredItems[index];
      const result = skillMention.insert(item, (skill) => `/${skill.name} `);
      applyInsert(result);
    },
    [skillMention, applyInsert]
  );

  const handleKeyDownWithMentions = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (fileMention.show && fileMention.filteredItems.length > 0) {
        const handled = fileMention.handleKeyDown(e);
        if (handled) {
          if (e.key === "Enter" || e.key === "Tab") {
            handleFileSelect(fileMention.selectedIndex);
          }
          return;
        }
      }

      if (skillMention.show && skillMention.filteredItems.length > 0) {
        const handled = skillMention.handleKeyDown(e);
        if (handled) {
          if (e.key === "Enter" || e.key === "Tab") {
            handleSkillSelect(skillMention.selectedIndex);
          }
          return;
        }
      }

      onKeyDown(e);
    },
    [fileMention, skillMention, handleFileSelect, handleSkillSelect, onKeyDown]
  );

  const handleVoiceRecording = async () => {
    if (isRecording) {
      try {
        setProcessing(true);
        const audioBlob = await stopRecording();
        const result = await api.transcribeAudio(audioBlob);
        onInputChange(inputValue + (inputValue ? ' ' : '') + result.text);
        textareaRef.current?.focus();
      } catch (err) {
        console.error('Failed to transcribe audio:', err);
      } finally {
        setProcessing(false);
      }
    } else {
      try {
        await startRecording();
      } catch (err) {
        console.error('Failed to start recording:', err);
      }
    }
  };

  const showFileDropdown = fileMention.show && fileMention.filteredItems.length > 0;
  const showSkillDropdown = skillMention.show && skillMention.filteredItems.length > 0 && !showFileDropdown;

  return (
    <div
      className="sticky bottom-0 z-20 shrink-0 bg-background"
      style={{ borderTop: "1px solid rgb(var(--cp-rgb-yellow) / 0.15)" }}
    >
      <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6">
        {isEditingMode && (
          <div
            className="mb-3 flex items-center justify-between border px-3 py-2 cp-cut-10"
            style={{
              borderColor: "rgb(var(--cp-rgb-cyan) / 0.3)",
              background: "rgb(var(--cp-rgb-cyan) / 0.06)",
            }}
          >
            <span className="cp-label" style={{ color: 'var(--color-cp-cyan)' }}>Editing message...</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => onCancelEdit?.()}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Cancel edit</span>
            </Button>
          </div>
        )}
        
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div
            className="flex items-center gap-1.5 border px-2 py-1 cp-cut-8"
            style={{
              borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)",
              background: "rgb(var(--cp-rgb-yellow) / 0.04)",
            }}
          >
            <Bot className="h-3.5 w-3.5 text-primary/60" />
            <span className="cp-label" style={{ color: 'var(--color-cp-yellow)' }}>{formatModelLabel(chatSettings.baseModel)}</span>
          </div>
          {chatSettings.enabledTools.length > 0 && (
            <div
              className="flex items-center gap-1.5 border px-2 py-1 cp-cut-8"
              style={{
              borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)",
              background: "rgb(var(--cp-rgb-yellow) / 0.04)",
            }}
            >
              <Zap className="h-3.5 w-3.5 text-primary/60" />
              <span className="cp-label text-muted-foreground">
                {chatSettings.enabledTools.map((t) => getToolLabel(t)).join(", ")}
              </span>
            </div>
          )}
        </div>

        <FileAttachments
          uploadedFiles={uploadedFiles}
          connectorEntries={connectorEntries}
          onRemoveFile={onRemoveFile}
          onRemoveConnectorEntry={onRemoveConnectorEntry}
          onEditConnectorEntry={onEditConnectorEntry}
        />

        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => handleInputChangeWithMentions(e.target.value)}
            onKeyDown={handleKeyDownWithMentions}
            placeholder="Type command..."
            className="typing-area min-h-[60px] resize-none pr-32 overflow-y-auto cp-cut-12 font-sans"
            style={{
              background: "var(--color-cp-surface3)",
            }}
            rows={1}
            disabled={isSending || !currentConversationId}
          />

          {showFileDropdown && (
            <MentionDropdown
              items={fileMention.filteredItems}
              selectedIndex={fileMention.selectedIndex}
              onSelect={handleFileSelect}
              onHover={(i) => fileMention.setSelectedIndex?.(i)}
              renderItem={(filePath, isSelected) => (
                <>
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span
                    className={`truncate font-medium ${isSelected ? "text-primary" : ""}`}
                    style={{ letterSpacing: "0.04em" }}
                  >
                    {filePath}
                  </span>
                </>
              )}
            />
          )}

          {showSkillDropdown && (
            <MentionDropdown
              items={skillMention.filteredItems}
              selectedIndex={skillMention.selectedIndex}
              onSelect={handleSkillSelect}
              onHover={(i) => skillMention.setSelectedIndex?.(i)}
              renderItem={(skill, isSelected) => (
                <>
                  <Slash className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span
                    className={`truncate font-medium ${isSelected ? "text-primary" : ""}`}
                    style={{ letterSpacing: "0.04em" }}
                  >
                    {skill.name}
                  </span>
                </>
              )}
            />
          )}

          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={onFileChange}
          />

          <div className="absolute bottom-2 right-2 flex gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-9 w-9"
                  disabled={isSending || isUploadingFiles || !currentConversationId}
                >
                  <Plus className="h-5 w-5" />
                  <span className="sr-only">Add attachments</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top">
                <DropdownMenuItem onClick={onFileUploadClick} disabled={isUploadingFiles}>
                  <Upload className="mr-2 h-4 w-4" />
                  <span>{isUploadingFiles ? "Uploading..." : "Upload files"}</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={onConnectorDialogOpen}>
                  <LinkIcon className="mr-2 h-4 w-4" />
                  <span>Add from Connector</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              size="icon"
              variant={isRecording ? "destructive" : "ghost"}
              className="h-9 w-9"
              onClick={handleVoiceRecording}
              disabled={isSending || isProcessing || !currentConversationId}
            >
              {isRecording ? (
                <Square className="h-5 w-5" />
              ) : (
                <Mic className="h-5 w-5" />
              )}
              <span className="sr-only">
                {isRecording ? 'Stop recording' : 'Start voice recording'}
              </span>
            </Button>
            <ChatSettingsDialog
              settings={chatSettings}
              onSettingsChange={onSettingsChange}
              currentChatId={currentConversationId}
              onChatUpdated={onChatUpdated}
            />
            <Button
              size="icon"
              className="h-9 w-9"
              type="submit"
              onClick={onSend}
              disabled={isSending || !currentConversationId || !inputValue.trim()}
            >
              <Send className="h-5 w-5" />
              <span className="sr-only">{isEditingMode ? 'Update message' : 'Send message'}</span>
            </Button>
          </div>
        </div>

        <p className="mt-2 cp-label text-muted-foreground">
          Enter to transmit / Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
