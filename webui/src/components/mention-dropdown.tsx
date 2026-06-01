import { useEffect, useRef, type ReactNode } from "react";

interface MentionDropdownProps<T> {
  items: T[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onHover: (index: number) => void;
  renderItem: (item: T, isSelected: boolean) => ReactNode;
}

export function MentionDropdown<T>({
  items,
  selectedIndex,
  onSelect,
  onHover,
  renderItem,
}: MentionDropdownProps<T>) {
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
