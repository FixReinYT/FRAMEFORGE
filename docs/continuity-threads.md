# Continuity Threads — design rationale

## Candidate concepts considered

### A. Continuity Threads — selected
A named landmark can be placed on a drawing in any frame. Examples: left eye, right wrist, top of the head, hand-held prop, foot contact point. The editor stores the coordinate for each frame and draws a color-coded trajectory overlay while the artist works.

**Problem solved:** in hand-drawn animation, a character can drift unintentionally between cels. Onion skin helps compare adjacent drawings, but it does not identify which exact feature is being tracked across a long sequence.

### B. Motion-path tweening
The artist draws a path and the application automatically moves or interpolates an object along it.

**Why not selected:** this is a mature animation pattern and overlaps with existing motion-guide/keyframe workflows. It would also require object isolation and interpolation semantics that the current raster-cel model does not provide.

### C. Reference/light-table board
The artist pins drawings or imported references beside the canvas and aligns them while drawing.

**Why not selected:** useful, but established animation applications already provide light-table/reference workflows. It is less distinctive for FRAMEFORGE than a project-native named landmark map.

## Comparison with documented workflows

- Krita documents onion-skin overlays for seeing adjacent animation frames: https://docs.krita.org/en/reference_manual/dockers/onion_skin.html
- Clip Studio Paint documents light-table layers and registering onion-skin images as references: https://help.clip-studio.com/en-us/manual_en/600_animation/Using_light_table_layers.htm
- Procreate Dreams documents motion keyframes that automatically tween movement, scale, warp and distortion: https://help.procreate.com/articles/deylln-animating-motion-with-keyframes
- Adobe Animate documents motion guides that define a path for an animated object: https://helpx.adobe.com/animate/desktop/animation/animation-guide.html

These references show that onion skin, light tables, keyframes and motion guides are established capabilities. FRAMEFORGE does not claim that landmark tracking is globally unprecedented. Its chosen distinction is a lightweight, named, per-feature continuity overlay designed specifically for manually drawn raster cels.

## Implemented interaction

1. Open the Нити tab in the editor's right dock.
2. Create a named thread, such as «Левый глаз».
3. Select the Нить непрерывности tool.
4. Click the same visual landmark in each frame where it needs to be checked.
5. Enable or disable trajectory visibility without changing the artwork.
6. Clear one frame's point or remove the whole thread.

## Data and safety properties

- Coordinates are project-space integer pixels, independent of zoom and pan.
- The overlay is display-only; it never paints onto a raster layer.
- Tracks are stored in the optional continuity_tracks field of the FFG manifest.
- Old FFG projects without that field load with an empty track collection.
- Frame insertion, duplication and deletion remap the stored frame indices.
- Track edits participate in the editor's Undo/Redo history.
- The loader validates track names, colors, frame indices and canvas coordinates before accepting metadata.
