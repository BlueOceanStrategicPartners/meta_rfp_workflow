import type { KeyboardEvent, ReactNode } from "react";
import { errorMessage } from "../../lib/adminApi";
import LoadState from "./LoadState";

export type AdminColumn<T> = {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** Right-aligned, tabular numbers. */
  numeric?: boolean;
  className?: string;
};

type Props<T> = {
  columns: AdminColumn<T>[];
  rows: T[] | null | undefined;
  rowKey: (row: T) => string;
  /** Accessible table name. */
  caption: string;
  onRowClick?: (row: T) => void;
  rowLabel?: (row: T) => string;
  rowClassName?: (row: T) => string;
  selectedKey?: string | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  errorTitle?: string;
  /** What will appear here and how to make the first one. */
  empty: ReactNode;
  /** Max height before the table scrolls inside its panel (CSS value). */
  maxHeight?: string;
};

/** Table with built-in loading / empty / error states. Scrolls inside itself, never the page. */
export default function AdminTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  onRowClick,
  rowLabel,
  rowClassName,
  selectedKey,
  loading,
  error,
  onRetry,
  errorTitle,
  empty,
  maxHeight,
}: Props<T>) {
  const hasRows = !!rows && rows.length > 0;

  if (!hasRows) {
    if (error) return <LoadState error={error} onRetry={onRetry} errorTitle={errorTitle} />;
    if (loading || !rows) return <LoadState loading />;
    return <div className="studio-empty-list">{empty}</div>;
  }

  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (!onRowClick) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowClick(row);
    }
  };

  return (
    <div className="space-y-2">
      {error ? (
        <div className="admin-alert admin-alert--warning flex flex-wrap items-center justify-between gap-2" role="status">
          <span>Couldn't refresh, showing the last data we had. {errorMessage(error)}</span>
          {onRetry ? (
            <button type="button" className="studio-btn-secondary admin-btn-small" onClick={onRetry}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}
      <div className="admin-table-wrap studio-scroll" style={maxHeight ? { maxHeight } : undefined}>
        <table className="admin-table">
          <caption className="admin-sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={`${c.numeric ? "is-num" : ""} ${c.className ?? ""}`}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows!.map((row) => {
              const key = rowKey(row);
              const classes = [
                onRowClick ? "is-clickable" : "",
                selectedKey && selectedKey === key ? "is-selected" : "",
                rowClassName?.(row) ?? "",
              ].join(" ");
              return (
                <tr
                  key={key}
                  className={classes}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={onRowClick ? (e) => onKey(e, row) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  title={onRowClick && rowLabel ? rowLabel(row) : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={`${c.numeric ? "is-num" : ""} ${c.className ?? ""}`}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
