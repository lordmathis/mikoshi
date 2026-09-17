import { Send, Bot, Zap, Plus, Upload, Link as LinkIcon, Mic, Square, File, FileText, Slash, X } from "lucide-react";
import { useEffect, useState, useCallback, useRef, type ReactNode } from "react";
import { Button } from "../ui/button.tsx";
import { Textarea } from "../ui/textarea.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu.tsx";
import { ChatSettingsDialog, type ChatSettings } from "./chat-settings-dialog.tsx";
import { Chip } from "../shared/chip.tsx";
import { getToolLabel, formatModelLabel } from "../lib/formatters.ts";
import { useVoiceRecording } from "./use-voice-recording.ts";
import { useMentionTrigger } from "./use-mention-trigger.ts";
import { api, type Skill, type ConnectorEntry, type FileResource } from "../lib/api.ts";

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
  uploadedFiles: FileResource[];
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
          <Chip
            style={{
              borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)",
              background: "rgb(var(--cp-rgb-yellow) / 0.04)",
            }}
            icon={<Bot className="h-3.5 w-3.5 text-primary/60" />}
            label={formatModelLabel(chatSettings.baseModel)}
            labelClassName="cp-label"
            labelStyle={{ color: 'var(--color-cp-yellow)' }}
          />
          {chatSettings.enabledTools.length > 0 && (
            <Chip
              style={{
                borderColor: "rgb(var(--cp-rgb-yellow) / 0.15)",
                background: "rgb(var(--cp-rgb-yellow) / 0.04)",
              }}
              icon={<Zap className="h-3.5 w-3.5 text-primary/60" />}
              label={chatSettings.enabledTools.map((t) => getToolLabel(t)).join(", ")}
              labelClassName="cp-label text-muted-foreground"
            />
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

function FileAttachments({
  uploadedFiles,
  connectorEntries,
  onRemoveFile,
  onRemoveConnectorEntry,
  onEditConnectorEntry,
}: {
  uploadedFiles: FileResource[];
  connectorEntries: ConnectorEntry[];
  onRemoveFile: (fileId: string) => void;
  onRemoveConnectorEntry: (connectorId: string, resourceId: string) => void;
  onEditConnectorEntry: (connectorId: string, resourceId: string) => void;
}) {
  if (uploadedFiles.length === 0 && connectorEntries.length === 0) {
    return null;
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {uploadedFiles.map((f, index) => (
        <Chip
          key={`${f.id}-${index}`}
          className="text-xs"
          style={{
            borderColor: "rgb(var(--cp-rgb-yellow) / 0.2)",
            background: "rgb(var(--cp-rgb-yellow) / 0.06)",
          }}
          icon={<File className="h-3.5 w-3.5 text-primary/70" />}
          label={f.filename}
          labelClassName="text-primary font-medium"
          actions={
            <button
              onClick={() => onRemoveFile(f.id)}
              className="ml-1 hover:text-[var(--color-cp-red)] transition-colors"
              aria-label={`Remove ${f.filename}`}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          }
        />
      ))}

      {connectorEntries.map((entry) => {
        const label = entry.resourceId.includes('/')
          ? entry.resourceId.split('/')[1]
          : entry.resourceId;

        return (
          <Chip
            key={`${entry.connectorId}-${entry.resourceId}`}
            className="text-xs"
            style={{
              borderColor: "rgb(var(--cp-rgb-cyan) / 0.2)",
              background: "rgb(var(--cp-rgb-cyan) / 0.06)",
            }}
            icon={<LinkIcon className="h-3.5 w-3.5 text-[var(--color-cp-cyan)]" />}
            labelClassName="text-[var(--color-cp-cyan)] font-medium"
            label={
              <>
                {entry.files.length} file{entry.files.length !== 1 ? "s" : ""} from{" "}
                {label}
              </>
            }
            actions={
              <>
                <button
                  onClick={() => onEditConnectorEntry(entry.connectorId, entry.resourceId)}
                  className="ml-1 hover:text-[var(--color-cp-cyan)]/80 transition-colors"
                  aria-label="Edit connector entry"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                  </svg>
                </button>
                <button
                  onClick={() => onRemoveConnectorEntry(entry.connectorId, entry.resourceId)}
                  className="ml-1 hover:text-[var(--color-cp-red)] transition-colors"
                  aria-label="Remove connector entry"
                  title="Remove connector entry"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </>
            }
          />
        );
      })}
    </div>
  );
}

function MentionDropdown<T>({
  items,
  selectedIndex,
  onSelect,
  onHover,
  renderItem,
}: {
  items: T[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onHover: (index: number) => void;
  renderItem: (item: T, isSelected: boolean) => ReactNode;
}) {
  return (
    <div
      className="absolute bottom-full left-0 mb-2 w-72 border shadow-lg z-50 bg-cp-surface3 cp-cut-x-10"
      style={{
        borderColor: "rgb(var(--cp-rgb-yellow) / 0.25)",
      }}
    >
      <div className="max-h-60 overflow-y-auto p-1">
        {items.map((item, index) => (
          <MentionItem
            key={index}
            index={index}
            selectedIndex={selectedIndex}
            onSelect={onSelect}
            onHover={onHover}
            renderItem={renderItem}
            item={item}
          />
        ))}
      </div>
    </div>
  );
}

function MentionItem<T>({
  index,
  selectedIndex,
  onSelect,
  onHover,
  renderItem,
  item,
}: {
  index: number;
  selectedIndex: number;
  onSelect: (index: number) => void;
  onHover: (index: number) => void;
  renderItem: (item: T, isSelected: boolean) => ReactNode;
  item: T;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const isSelected = index === selectedIndex;

  useEffect(() => {
    if (isSelected) {
      ref.current?.scrollIntoView({ block: "nearest" });
    }
  }, [isSelected]);

  return (
    <button
      ref={ref}
      type="button"
      className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors text-left ${
        isSelected
          ? "bg-primary/10 text-primary"
          : "hover:bg-primary/5 text-foreground"
      }`}
      onClick={() => onSelect(index)}
      onMouseEnter={() => onHover(index)}
    >
      {renderItem(item, isSelected)}
    </button>
  );
}
