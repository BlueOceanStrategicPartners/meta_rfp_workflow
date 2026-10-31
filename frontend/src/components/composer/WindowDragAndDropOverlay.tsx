type Props = {
  visible: boolean;
  onDrop: (files: FileList) => void;
};

export default function WindowDragAndDropOverlay({ visible, onDrop }: Props) {
  if (!visible) return null;
  return (
    <div
      className="fixed inset-0 z-40 bg-cyan-500/10 border-2 border-dashed border-cyan-400 flex items-center justify-center pointer-events-auto"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        if (e.dataTransfer.files.length) onDrop(e.dataTransfer.files);
      }}
    >
      <p className="text-cyan-200 text-lg">Drop RFP documents to ingest</p>
    </div>
  );
}
