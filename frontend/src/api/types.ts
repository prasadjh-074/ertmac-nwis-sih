// Manual TypeScript mirrors of the confirmed Pydantic models in backend/server.py.
export interface StatusCheck {
  id: string;
  client_name: string;
  timestamp: string;
}

export interface RootStatus {
  message: string;
}