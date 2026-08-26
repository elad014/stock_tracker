import type { EncryptedPayload, LoginPublicKey } from "../models/auth";

function bytesToBase64(bytes: Uint8Array): string {
  let binary: string = "";
  const chunkSize: number = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk: Uint8Array = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

function copyToArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buffer: ArrayBuffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return buffer;
}

async function importRsaPublicKey(publicJwk: LoginPublicKey): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "jwk",
    {
      kty: publicJwk.kty,
      n: publicJwk.n,
      e: publicJwk.e,
    },
    { name: "RSA-OAEP", hash: "SHA-256" },
    false,
    ["encrypt"],
  );
}

export async function encryptJsonPayload(
  payload: object,
  publicJwk: LoginPublicKey,
): Promise<EncryptedPayload> {
  const rsaKey: CryptoKey = await importRsaPublicKey(publicJwk);
  const aesKey: CryptoKey = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt"],
  );
  const iv: Uint8Array = crypto.getRandomValues(new Uint8Array(12));
  const encoded: Uint8Array = new TextEncoder().encode(JSON.stringify(payload));
  const ciphertextBuffer: ArrayBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: copyToArrayBuffer(iv) },
    aesKey,
    copyToArrayBuffer(encoded),
  );
  const rawAes: ArrayBuffer = await crypto.subtle.exportKey("raw", aesKey);
  const wrappedBuffer: ArrayBuffer = await crypto.subtle.encrypt(
    { name: "RSA-OAEP" },
    rsaKey,
    rawAes,
  );
  return {
    wrapped_key: bytesToBase64(new Uint8Array(wrappedBuffer)),
    iv: bytesToBase64(iv),
    ciphertext: bytesToBase64(new Uint8Array(ciphertextBuffer)),
  };
}
