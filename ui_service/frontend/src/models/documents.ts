export type DocumentNodeType = "file" | "folder";

export type TreeNode = {
  name: string;
  path: string;
  type: DocumentNodeType;
  size: number | null;
  last_modified: string | null;
  children: TreeNode[];
};

export type DocumentTree = {
  nodes: TreeNode[];
  file_count: number;
  max_files: number;
};
