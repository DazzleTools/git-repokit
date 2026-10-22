/**
 * __RK_DESCRIPTION__
 *
 * The package's public surface. Everything exported here is what
 * `import ... from "__RK_PROJECT__"` gives a consumer.
 */

export const name = "__RK_PROJECT__";

/** A first function to replace with the package's work. */
export function greet(who = "world"): string {
  return `Hello, ${who}, from ${name}.`;
}
