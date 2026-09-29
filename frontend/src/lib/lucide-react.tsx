// lucide-react 1.x removed brand logos (lucide-icons/lucide#670: "use Simple Icons"), yet
// `import { Instagram } from "lucide-react"` is what most code, and every model, still writes.
// Vite and tsconfig alias "lucide-react" here: everything from the real package, plus the removed
// names backed by Simple Icons, or lucide's own 0.x glyph (ISC) where Simple Icons has no mark.
// New code should import the Si* components from "@icons-pack/react-simple-icons" directly.
/* oxlint-disable react/only-export-components -- every export here is an icon component */
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { createLucideIcon, type LucideProps } from "lucide-react-upstream";
import {
  SiCodesandbox,
  SiDribbble,
  SiFacebook,
  SiFigma,
  SiFramer,
  SiGithub,
  SiGitlab,
  SiGooglechrome,
  SiInstagram,
  SiTrello,
  SiTwitch,
  SiX,
  SiYoutube,
  type IconType,
} from "@icons-pack/react-simple-icons";

export * from "lucide-react-upstream";

type IconNode = Parameters<typeof createLucideIcon>[1];

function fromSimpleIcons(name: string, Si: IconType) {
  const Brand = forwardRef<SVGSVGElement, LucideProps>(function Brand(props, ref) {
    // Simple Icons marks are filled shapes: lucide's stroke props mean nothing on them.
    const { size = 24, color = "currentColor", strokeWidth, absoluteStrokeWidth, ...rest } = props;
    void strokeWidth;
    void absoluteStrokeWidth;
    return <Si ref={ref} size={size} color={color} {...(rest as ComponentPropsWithoutRef<IconType>)} />;
  });
  Brand.displayName = name;
  return Brand;
}

export const Chrome = fromSimpleIcons("Chrome", SiGooglechrome);
export const Codesandbox = fromSimpleIcons("Codesandbox", SiCodesandbox);
export const Dribbble = fromSimpleIcons("Dribbble", SiDribbble);
export const Facebook = fromSimpleIcons("Facebook", SiFacebook);
export const Figma = fromSimpleIcons("Figma", SiFigma);
export const Framer = fromSimpleIcons("Framer", SiFramer);
export const Github = fromSimpleIcons("Github", SiGithub);
export const Gitlab = fromSimpleIcons("Gitlab", SiGitlab);
export const Instagram = fromSimpleIcons("Instagram", SiInstagram);
export const Trello = fromSimpleIcons("Trello", SiTrello);
export const Twitch = fromSimpleIcons("Twitch", SiTwitch);
export const Twitter = fromSimpleIcons("Twitter", SiX); // the mark is X now
export const Youtube = fromSimpleIcons("Youtube", SiYoutube);

// Simple Icons carries no mark for these (brand-owner requests): lucide 0.577 glyphs, ISC.
const LINKEDIN: IconNode = [
  ["path", { d: "M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z", key: "c2jq9f" }],
  ["rect", { width: "4", height: "12", x: "2", y: "9", key: "mk3on5" }],
  ["circle", { cx: "4", cy: "4", r: "2", key: "bt5ra8" }],
];
const SLACK: IconNode = [
  ["rect", { width: "3", height: "8", x: "13", y: "2", rx: "1.5", key: "diqz80" }],
  ["path", { d: "M19 8.5V10h1.5A1.5 1.5 0 1 0 19 8.5", key: "183iwg" }],
  ["rect", { width: "3", height: "8", x: "8", y: "14", rx: "1.5", key: "hqg7r1" }],
  ["path", { d: "M5 15.5V14H3.5A1.5 1.5 0 1 0 5 15.5", key: "76g71w" }],
  ["rect", { width: "8", height: "3", x: "14", y: "13", rx: "1.5", key: "1kmz0a" }],
  ["path", { d: "M15.5 19H14v1.5a1.5 1.5 0 1 0 1.5-1.5", key: "jc4sz0" }],
  ["rect", { width: "8", height: "3", x: "2", y: "8", rx: "1.5", key: "1omvl4" }],
  ["path", { d: "M8.5 5H10V3.5A1.5 1.5 0 1 0 8.5 5", key: "16f3cl" }],
];
const POCKET: IconNode = [
  ["path", { d: "M20 3a2 2 0 0 1 2 2v6a1 1 0 0 1-20 0V5a2 2 0 0 1 2-2z", key: "1uodqw" }],
  ["path", { d: "m8 10 4 4 4-4", key: "1mxd5q" }],
];
const CODEPEN: IconNode = [
  ["polygon", { points: "12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2", key: "srzb37" }],
  ["line", { x1: "12", x2: "12", y1: "22", y2: "15.5", key: "1t73f2" }],
  ["polyline", { points: "22 8.5 12 15.5 2 8.5", key: "ajlxae" }],
  ["polyline", { points: "2 15.5 12 8.5 22 15.5", key: "susrui" }],
  ["line", { x1: "12", x2: "12", y1: "2", y2: "8.5", key: "2cldga" }],
];
const CHROMIUM: IconNode = [
  ["path", { d: "M10.88 21.94 15.46 14", key: "xkve6t" }],
  ["path", { d: "M21.17 8H12", key: "19dcdn" }],
  ["path", { d: "M3.95 6.06 8.54 14", key: "g8jz9m" }],
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["circle", { cx: "12", cy: "12", r: "4", key: "4exip2" }],
];
export const Linkedin = createLucideIcon("linkedin", LINKEDIN);
export const Slack = createLucideIcon("slack", SLACK);
export const Pocket = createLucideIcon("pocket", POCKET);
export const Codepen = createLucideIcon("codepen", CODEPEN);
export const Chromium = createLucideIcon("chromium", CHROMIUM);

// lucide exposes every icon under three names; keep all three for the restored ones.
export {
  Chrome as ChromeIcon, Chrome as LucideChrome,
  Chromium as ChromiumIcon, Chromium as LucideChromium,
  Codepen as CodepenIcon, Codepen as LucideCodepen,
  Codesandbox as CodesandboxIcon, Codesandbox as LucideCodesandbox,
  Dribbble as DribbbleIcon, Dribbble as LucideDribbble,
  Facebook as FacebookIcon, Facebook as LucideFacebook,
  Figma as FigmaIcon, Figma as LucideFigma,
  Framer as FramerIcon, Framer as LucideFramer,
  Github as GithubIcon, Github as LucideGithub,
  Gitlab as GitlabIcon, Gitlab as LucideGitlab,
  Instagram as InstagramIcon, Instagram as LucideInstagram,
  Linkedin as LinkedinIcon, Linkedin as LucideLinkedin,
  Pocket as PocketIcon, Pocket as LucidePocket,
  Slack as SlackIcon, Slack as LucideSlack,
  Trello as TrelloIcon, Trello as LucideTrello,
  Twitch as TwitchIcon, Twitch as LucideTwitch,
  Twitter as TwitterIcon, Twitter as LucideTwitter,
  Youtube as YoutubeIcon, Youtube as LucideYoutube,
};
