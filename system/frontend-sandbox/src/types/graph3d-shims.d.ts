declare module 'three' {
  export class SphereGeometry {
    constructor(radius?: number, widthSegments?: number, heightSegments?: number)
  }

  export class MeshLambertMaterial {
    constructor(parameters?: Record<string, unknown>)
  }

  export class Mesh {
    constructor(geometry?: unknown, material?: unknown)
  }
}

declare module 'three-spritetext' {
  export default class SpriteText {
    constructor(text?: string)
    color: string
    textHeight: number
    backgroundColor: string
    padding: number
  }
}
