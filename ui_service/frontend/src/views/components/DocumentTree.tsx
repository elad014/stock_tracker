import type { TreeNode } from "../../models/documents";

type DocumentTreeProps = {
  nodes: TreeNode[];
  selectedFolder: string;
  expanded: Record<string, boolean>;
  busy: boolean;
  depth?: number;
  onToggleFolder: (path: string) => void;
  onSelectFolder: (path: string) => void;
  onOpenFile: (node: TreeNode) => void;
  onMoveFile: (node: TreeNode) => void;
  onDelete: (node: TreeNode) => void;
};

function formatSize(size: number | null): string {
  if (size === null || size === undefined) {
    return "";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(0)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentTree({
  nodes,
  selectedFolder,
  expanded,
  busy,
  depth = 0,
  onToggleFolder,
  onSelectFolder,
  onOpenFile,
  onMoveFile,
  onDelete,
}: DocumentTreeProps): JSX.Element {
  return (
    <ul className="doc-tree" role={depth === 0 ? "tree" : "group"}>
      {nodes.map((node: TreeNode) => {
        const isFolder: boolean = node.type === "folder";
        const isOpen: boolean = expanded[node.path] === true;
        const isSelected: boolean = isFolder && selectedFolder === node.path;

        return (
          <li key={node.path} className="doc-tree-node" role="treeitem">
            <div
              className={isSelected ? "doc-row doc-row-selected" : "doc-row"}
              style={{ paddingLeft: `${depth * 0.85 + 0.4}rem` }}
            >
              {isFolder ? (
                <button
                  type="button"
                  className="doc-caret"
                  onClick={() => onToggleFolder(node.path)}
                  aria-label={isOpen ? `Collapse ${node.name}` : `Expand ${node.name}`}
                  aria-expanded={isOpen}
                >
                  {isOpen ? "-" : "+"}
                </button>
              ) : (
                <span className="doc-caret doc-caret-file" aria-hidden="true">
                  .
                </span>
              )}

              <button
                type="button"
                className="doc-label"
                onClick={() =>
                  isFolder ? onSelectFolder(node.path) : onOpenFile(node)
                }
                title={isFolder ? "Select folder" : "Open file"}
              >
                <span className={isFolder ? "doc-name doc-name-folder" : "doc-name"}>
                  {node.name}
                </span>
                {!isFolder && <span className="doc-size">{formatSize(node.size)}</span>}
              </button>

              {!isFolder && (
                <button
                  type="button"
                  className="doc-move"
                  onClick={() => onMoveFile(node)}
                  disabled={busy}
                  aria-label={`Move ${node.name}`}
                  title="Move to the folder in Put files in"
                >
                  Move
                </button>
              )}

              <button
                type="button"
                className="doc-delete"
                onClick={() => onDelete(node)}
                disabled={busy}
                aria-label={`Delete ${node.name}`}
                title={
                  isFolder ? "Delete folder (must be empty)" : "Delete file"
                }
              >
                x
              </button>
            </div>

            {isFolder && isOpen && node.children.length > 0 && (
              <DocumentTree
                nodes={node.children}
                selectedFolder={selectedFolder}
                expanded={expanded}
                busy={busy}
                depth={depth + 1}
                onToggleFolder={onToggleFolder}
                onSelectFolder={onSelectFolder}
                onOpenFile={onOpenFile}
                onMoveFile={onMoveFile}
                onDelete={onDelete}
              />
            )}

            {isFolder && isOpen && node.children.length === 0 && (
              <p
                className="doc-empty-folder"
                style={{ paddingLeft: `${(depth + 1) * 0.85 + 1.6}rem` }}
              >
                Empty
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
