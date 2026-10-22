import { useEffect, useMemo } from "react";
import { type Sheet, saveBlob } from "./api";

type Props = { sheet: Sheet; index: number; total: number; zoom: "fit" | "actual"; stale: boolean; filename: string };

export function SheetView({ sheet, index, total, zoom, stale, filename }: Props) {
  const blob = useMemo(() => new Blob([sheet.svg], { type: "image/svg+xml" }), [sheet.svg]);
  const url = useMemo(() => URL.createObjectURL(blob), [blob]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);

  const aspect = sheet.width / sheet.height;
  // Fit: as large as the viewport height allows, never wider than the stage.
  const width = zoom === "actual" ? `${sheet.width}mm` : `min(100%, calc((100vh - 150px) * ${aspect}))`;

  return (
    <figure className={`sheet ${stale ? "stale" : ""}`} style={{ width }}>
      <div className="paper" style={{ aspectRatio: `${sheet.width} / ${sheet.height}` }}>
        <img src={url} alt={`Sheet ${index + 1} of ${total}`} />
      </div>
      <figcaption>
        <span>
          {total > 1 && <b>Sheet {index + 1}</b>} {sheet.width.toFixed(0)} × {sheet.height.toFixed(0)} mm · {sheet.pieces}{" "}
          {sheet.pieces === 1 ? "piece" : "pieces"}
        </span>
        <button className="link" onClick={() => saveBlob(blob, filename)}>
          SVG
        </button>
      </figcaption>
    </figure>
  );
}
