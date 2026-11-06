/** The capture written by record.mjs (timeline.json). All times are seconds from frame 0. */
export type Box = { x: number; y: number; w: number; h: number };
export type Point = { x: number; y: number };

export type Timeline = {
  version: number;
  slug: string;
  title: string;
  subtitle: string | null;
  app: string | null;
  accent: string;
  viewport: { width: number; height: number };
  dsf: number;
  duration: number;
  cursorStart: Point;
  frames: { file: string; t: number; hi?: boolean }[];
  steps: {
    i: number;
    text: string;
    action: string;
    t0: number;
    t1: number;
    box: Box | null;
    /** Where the framed element sat after the action moved the page (the ring glides there from `t`). */
    boxAfter?: (Box & { t: number }) | null;
    /** The framed element was gone after the action: the ring fades out from this time. */
    boxEnd?: number | null;
    /** false keeps the camera wide; a number forces that zoom. */
    zoom: number | false | null;
  }[];
  moves: { t0: number; t1: number; from: Point; to: Point }[];
  clicks: { t: number; x: number; y: number }[];
  navs: { t: number; url: string }[];
};

export type Props = {
  timeline: Timeline;
  /** staticFile() folder holding frames/ (public/<base>/frames/...). */
  base: string;
  titleSec: number;
};
