"use client";
/** Client island of /assistant: both rule-based tools (AIX-01…03). */
import { BoardSizeTool } from "./BoardSizeTool";
import { RecommendTool, type RegionOption } from "./RecommendTool";
import type { BoardValues, RecommendValues } from "./assistantModel";
import "./assistant.css";

export function AssistantTools({
  regions,
  hazardLabels,
  initialBoard,
  initialRecommend,
}: {
  regions: RegionOption[];
  hazardLabels: Record<string, string>;
  initialBoard?: BoardValues;
  initialRecommend?: RecommendValues;
}) {
  return (
    <div className="gv-ax-tools">
      <div id="recommend">
        <RecommendTool regions={regions} hazardLabels={hazardLabels} initial={initialRecommend} />
      </div>
      <div id="board-size">
        <BoardSizeTool initial={initialBoard} />
      </div>
    </div>
  );
}
