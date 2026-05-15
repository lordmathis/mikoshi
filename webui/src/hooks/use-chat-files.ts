import { useState } from "react";
import { api, type FileResource, type ConnectorEntry } from "../lib/api";

export function useChatFiles() {
  const [uploadedFiles, setUploadedFiles] = useState<FileResource[]>([]);
  const [connectorEntries, setConnectorEntries] = useState<ConnectorEntry[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const uploadFiles = async (files: File[]) => {
    setIsUploading(true);
    try {
      const uploaded = await api.uploadFiles(files);
      setUploadedFiles((prev) => [...prev, ...uploaded]);
    } finally {
      setIsUploading(false);
    }
  };

  const addConnectorEntry = (entry: ConnectorEntry) => {
    setConnectorEntries((prev) => [...prev, entry]);
  };

  const updateConnectorEntry = async (
    connectorId: string,
    resourceId: string,
    newEntry: ConnectorEntry
  ) => {
    const oldEntry = connectorEntries.find(
      (e) => e.connectorId === connectorId && e.resourceId === resourceId
    );
    if (oldEntry) {
      for (const file of oldEntry.files) {
        try {
          await api.deleteFile(file.id);
        } catch (error) {
          console.error("Failed to delete file:", error);
        }
      }
    }
    setConnectorEntries((prev) =>
      prev.map((e) =>
        e.connectorId === connectorId && e.resourceId === resourceId ? newEntry : e
      )
    );
  };

  const removeConnectorEntry = async (connectorId: string, resourceId: string) => {
    const entry = connectorEntries.find(
      (e) => e.connectorId === connectorId && e.resourceId === resourceId
    );
    if (entry) {
      for (const file of entry.files) {
        try {
          await api.deleteFile(file.id);
        } catch (error) {
          console.error("Failed to delete file:", error);
        }
      }
    }
    setConnectorEntries((prev) =>
      prev.filter((e) => !(e.connectorId === connectorId && e.resourceId === resourceId))
    );
  };

  const removeFile = async (id: string) => {
    try {
      await api.deleteFile(id);
      setUploadedFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (error) {
      console.error("Failed to remove file:", error);
      setUploadedFiles((prev) => prev.filter((f) => f.id !== id));
    }
  };

  const clearAll = () => {
    setUploadedFiles([]);
    setConnectorEntries([]);
  };

  const getAllFiles = (): FileResource[] => {
    return [...uploadedFiles, ...connectorEntries.flatMap((e) => e.files)];
  };

  return {
    uploadedFiles,
    connectorEntries,
    isUploading,
    uploadFiles,
    addConnectorEntry,
    updateConnectorEntry,
    removeConnectorEntry,
    removeFile,
    clearAll,
    getAllFiles,
  };
}