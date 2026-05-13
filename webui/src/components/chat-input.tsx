import { Send, Bot, Zap, Plus, Upload, Link as LinkIcon, Mic, Square, AtSign, X } from "lucide-react";
import { useEffect, useState } from "react";
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
import { getToolLabel } from "../lib/formatters";
import { useVoiceRecording } from "../hooks/use-voice-recording";
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
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSearch, setMentionSearch] = useState("");
  const [mentionStart, setMentionStart] = useState(-1);
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(0);

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

  const filteredSkills = skills.filter(skill => 
    skill.name.toLowerCase().includes(mentionSearch.toLowerCase())
  );

  useEffect(() => {
    if (recordingError) {
      console.error('Voice recording error:', recordingError);
      setTimeout(clearError, 5000);
    }
  }, [recordingError, clearError]);

  const handleInputChangeWithMentions = (value: string) => {
    onInputChange(value);
    
    const cursorPos = textareaRef.current?.selectionStart || 0;
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex !== -1) {
      const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
      if (!textAfterAt.includes(' ') && !textAfterAt.includes('\n')) {
        setShowMentions(true);
        setMentionSearch(textAfterAt);
        setMentionStart(lastAtIndex);
        setSelectedMentionIndex(0);
        return;
      }
    }
    
    setShowMentions(false);
  };

  const insertMention = (skillName: string) => {
    if (mentionStart === -1) return;
    const before = inputValue.substring(0, mentionStart);
    const after = inputValue.substring(mentionStart + 1 + mentionSearch.length);
    onInputChange(`${before}@${skillName} ${after}`);
    setShowMentions(false);
    setTimeout(() => {
      const pos = mentionStart + skillName.length + 2;
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(pos, pos);
    }, 0);
  };

  const handleKeyDownWithMentions = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showMentions && filteredSkills.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedMentionIndex(prev => Math.min(prev + 1, filteredSkills.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedMentionIndex(prev => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(filteredSkills[selectedMentionIndex].name);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowMentions(false);
        return;
      }
    }
    
    onKeyDown(e);
  };

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

  return (
    <div
      className="sticky bottom-0 z-20 shrink-0 bg-[#0a0a0c]"
      style={{ borderTop: "1px solid rgba(245, 216, 0, 0.15)" }}
    >
      <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6">
        {isEditingMode && (
          <div
            className="mb-3 flex items-center justify-between border px-3 py-2"
            style={{
              borderColor: "rgba(0, 212, 255, 0.3)",
              background: "rgba(0, 212, 255, 0.06)",
              clipPath: "polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%)",
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
            className="flex items-center gap-1.5 border px-2 py-1"
            style={{
              borderColor: "rgba(245, 216, 0, 0.15)",
              background: "rgba(245, 216, 0, 0.04)",
              clipPath: "polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)",
            }}
          >
            <Bot className="h-3.5 w-3.5 text-primary/60" />
            <span className="cp-label" style={{ color: '#f5d800' }}>{chatSettings.baseModel.includes(':') ? chatSettings.baseModel.split(':').slice(1).join(':') : chatSettings.baseModel}</span>
          </div>
          {chatSettings.enabledTools.length > 0 && (
            <div
              className="flex items-center gap-1.5 border px-2 py-1"
              style={{
                borderColor: "rgba(245, 216, 0, 0.15)",
                background: "rgba(245, 216, 0, 0.04)",
                clipPath: "polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)",
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
            className="typing-area min-h-[60px] resize-none pr-32 overflow-y-auto"
            style={{
              clipPath: "polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%)",
              background: "#10100e",
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            }}
            rows={1}
            disabled={isSending || !currentConversationId}
          />

          {showMentions && filteredSkills.length > 0 && (
            <div
              className="absolute bottom-full left-0 mb-2 w-64 border shadow-lg z-50 bg-[#10100e]"
              style={{
                clipPath: "polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))",
                borderColor: "rgba(245, 216, 0, 0.25)",
              }}
            >
              <div className="max-h-60 overflow-y-auto p-1">
                {filteredSkills.map((skill, index) => (
                  <button
                    key={skill.name}
                    type="button"
                    className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors text-left ${
                      index === selectedMentionIndex
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-primary/5 text-foreground'
                    }`}
                    onClick={() => insertMention(skill.name)}
                    onMouseEnter={() => setSelectedMentionIndex(index)}
                  >
                    <AtSign className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="truncate font-medium" style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>{skill.name}</span>
                  </button>
                ))}
              </div>
            </div>
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
