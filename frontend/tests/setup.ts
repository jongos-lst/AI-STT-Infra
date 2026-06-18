// jsdom's File doesn't implement arrayBuffer(). Polyfill via FileReader,
// which jsdom does ship, so SubtleCrypto helpers behave the same as in the browser.

const proto = (globalThis as { File?: typeof File }).File?.prototype as
  | (Blob & { arrayBuffer?: () => Promise<ArrayBuffer> })
  | undefined;
if (proto && typeof proto.arrayBuffer !== "function") {
  proto.arrayBuffer = function arrayBuffer(this: Blob) {
    return new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = () => reject(reader.error ?? new Error("FileReader failed"));
      reader.readAsArrayBuffer(this);
    });
  };
}
