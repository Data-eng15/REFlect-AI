import { initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const apiKey = import.meta.env.VITE_FIREBASE_API_KEY || "";

let firebaseApp: FirebaseApp | undefined;
export let auth: Auth | null = null;

if (apiKey) {
  firebaseApp = initializeApp({
    apiKey,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "",
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
    appId: import.meta.env.VITE_FIREBASE_APP_ID || "",
  });
  auth = getAuth(firebaseApp);
}
