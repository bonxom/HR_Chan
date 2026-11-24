import { useEffect, useRef, useState, type FC } from 'react';
import { useNavigate } from 'react-router';
import { CornerDownLeft, Search, type LucideIcon } from 'lucide-react';
import { GLASS_LAYER } from './Glass';

export interface CommandItem {
  label: string;
  to: string;
  icon: LucideIcon;
  group: string;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
}

function normalize(text: string) {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase();
}

/** Ctrl/⌘ K quick navigation between the pages the current account can open. */
export const CommandPalette: FC<CommandPaletteProps> = ({ open, onClose, items }) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActive(0);
    inputRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const text = normalize(query.trim());
  const results = items.filter((item) => !text || normalize(item.label).includes(text));

  const go = (item: CommandItem | undefined) => {
    if (!item) return;
    onClose();
    navigate(item.to);
  };

  return (
    <div className="fixed inset-0 z-[70] flex justify-center px-4 pt-[14vh]" role="dialog" aria-modal="true" aria-label="Đi tới trang">
      <button
        type="button"
        aria-label="Đóng"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-ink/15 backdrop-blur-[2px]"
      />
      <div className={`relative h-fit w-full max-w-lg overflow-hidden rounded-2xl ${GLASS_LAYER}`}>
        <label className="flex items-center gap-3 border-b border-line/80 px-4">
          <Search className="h-4 w-4 shrink-0 text-ink-subtle" />
          <span className="sr-only">Tìm trang</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') onClose();
              if (event.key === 'ArrowDown') {
                event.preventDefault();
                setActive((index) => Math.min(index + 1, results.length - 1));
              }
              if (event.key === 'ArrowUp') {
                event.preventDefault();
                setActive((index) => Math.max(index - 1, 0));
              }
              if (event.key === 'Enter') go(results[active]);
            }}
            placeholder="Đi tới trang…"
            className="h-13 flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-subtle focus:outline-none"
          />
          <kbd className="rounded border border-line bg-surface/70 px-1.5 text-[11px] text-ink-muted">Esc</kbd>
        </label>
        <ul className="max-h-[50vh] overflow-y-auto p-2">
          {results.length === 0 && (
            <li className="px-3 py-8 text-center text-sm text-ink-muted">Không có trang nào khớp với “{query}”.</li>
          )}
          {results.map((item, index) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(index)}
                  onClick={() => go(item)}
                  className={`flex w-full cursor-pointer items-center gap-3 rounded-control px-3 py-2.5 text-left transition-colors ${
                    index === active ? 'bg-white/90 shadow-[0_1px_3px_rgba(15,60,50,0.12)]' : ''
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0 text-ink-subtle" />
                  <span className="truncate text-sm text-ink">{item.label}</span>
                  <span className="truncate text-xs text-ink-subtle">{item.group}</span>
                  {index === active && <CornerDownLeft className="ml-auto h-3.5 w-3.5 shrink-0 text-ink-subtle" />}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
};
