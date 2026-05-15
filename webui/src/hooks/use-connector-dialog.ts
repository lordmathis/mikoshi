import { useState } from "react";
import type { ConnectorEntry } from "../lib/api";

export function useConnectorDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<ConnectorEntry | null>(null);

  const openNew = () => {
    setEditingEntry(null);
    setIsOpen(true);
  };

  const openEdit = (entry: ConnectorEntry) => {
    setEditingEntry(entry);
    setIsOpen(true);
  };

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) setEditingEntry(null);
  };

  return {
    isOpen,
    editingEntry,
    openNew,
    openEdit,
    handleOpenChange,
  };
}
