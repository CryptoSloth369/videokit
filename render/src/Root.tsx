import React from "react";
import { Composition } from "remotion";
import { HowTo } from "./HowTo";
import type { Props } from "./types";

const FPS = 30;

/** Stand-in props so the studio opens without a capture; real renders pass --props. */
const placeholder: Props = {
  base: "capture/example",
  titleSec: 2.4,
  timeline: {
    version: 1,
    slug: "example",
    title: "Record a capture first",
    subtitle: "node record.mjs <step-file.json>",
    app: "howto-video",
    accent: "#1735BB",
    viewport: { width: 1440, height: 900 },
    dsf: 1.5,
    duration: 3,
    cursorStart: { x: 720, y: 450 },
    frames: [{ file: "missing.jpg", t: 0 }],
    steps: [],
    moves: [],
    clicks: [],
    navs: [],
  },
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="HowTo"
    component={HowTo}
    fps={FPS}
    width={1920}
    height={1080}
    durationInFrames={FPS * 5}
    defaultProps={placeholder}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.ceil((props.titleSec + props.timeline.duration + 0.2) * FPS),
    })}
  />
);
