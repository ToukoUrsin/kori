import React from 'react';
import {Composition} from 'remotion';
import {Film, SCENES, TOTAL} from './Film';
import {Take, TAKE_TOTAL} from './Take';

export const Root: React.FC = () => (
	<>
		<Composition id="Film" component={Film} durationInFrames={TOTAL} fps={30} width={1920} height={1080} defaultProps={{audio: true, captions: true}} />
		{/* the film cut around the founder's voice take (scripts/take-render.sh) */}
		<Composition id="Take" component={Take} durationInFrames={TAKE_TOTAL} fps={30} width={1920} height={1080} />
		{SCENES.map((s) => (
			<Composition key={s.id} id={`S-${s.id}`} component={s.C} durationInFrames={s.dur} fps={30} width={1920} height={1080} defaultProps={{dur: s.dur}} />
		))}
	</>
);
