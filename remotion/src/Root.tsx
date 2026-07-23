import React from "react";
import { Composition } from "remotion";
import { StoryNarrative, defaultStoryProps, type StoryProps } from "./StoryNarrative";

const FPS = 24;

export const RemotionRoot: React.FC = () => {
  const calcFrames = (props: StoryProps) =>
    Math.max(
      24,
      (props.shots || []).reduce(
        (acc, s) => acc + (s.durationFrames || Math.round((s.durationSec || 3) * FPS)),
        0
      )
    );

  return (
    <>
      <Composition
        id="StoryNarrative"
        component={StoryNarrative}
        durationInFrames={calcFrames(defaultStoryProps)}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={defaultStoryProps}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: calcFrames(props as StoryProps),
        })}
      />
    </>
  );
};
