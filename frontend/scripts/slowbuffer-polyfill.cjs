'use strict';
// Next 12 bundles jsonwebtoken -> buffer-eq, which expects `buffer.SlowBuffer`.
// Node 21+ removed SlowBuffer; assigning Buffer is sufficient for that code path.
const buffer = require('buffer');
if (buffer.SlowBuffer == null) {
  buffer.SlowBuffer = buffer.Buffer;
}
