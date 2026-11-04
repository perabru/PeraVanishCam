# Substitution log sprite

`substitution_log.png` was generated with the built-in ImageGen tool. The user
image was used as a visual reference for object shape and mood, not as an edit
target. The sprite is an original transparent-background illustration.

Final prompt:

> Create a single ORIGINAL 2D hand-painted anime-style game sprite for live video compositing, using the user's attached image ONLY as a visual reference for the object and mood. Subject: one short thick wooden substitution log floating diagonally (bottom-left to top-right), soft desaturated pale sage-green bark with visible wood grain, dark ink cracks and small dark notches, round cut end with concentric wood rings visible at lower-left. Dramatic clean silhouette, strong cel shading and highlights, polished Japanese animation look. Center the entire log, leave a modest transparent margin around all edges. NO smoke, NO particles, NO background, NO scenery, NO shadow outside the object, NO people, NO text, NO symbols or logos. True transparent alpha background; isolated cutout. Asset should be immediately usable as a sprite over live webcam video.

For smoke, the app uses its own procedurally animated shapes in
`naruto_effect.py`. A [CC0 smoke sprite sheet](https://opengameart.org/content/smoke-sprite-sheet)
was reviewed but is not included because the procedural smoke scales and follows
the detected person dynamically.

## Classic sprite quality update

The current sprite is a faithful ImageGen edit of the 1.0.1 illustration.
The same diagonal log, sage-green bark, ink cracks, cel shading and visible
wood rings are retained. The PNG uses true alpha. The renderer resizes with
premultiplied alpha to avoid edge halos and keeps a bounded size cache.

Edit prompt: Improve only the image fidelity of the original first-version log:
clean sharp contours, high-resolution linework, clearer wood grain, no noisy
fringe. Preserve its design, diagonal orientation, colors, proportions, cel
shading and framing. No photorealistic redesign, branches, smoke, ground, text
or additional objects. Entire object visible on a true transparent background.
