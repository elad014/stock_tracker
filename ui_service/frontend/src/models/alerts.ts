export type AlertType = "ABSOLUTE" | "PERCENT";
export type AlertDirection = "ABOVE" | "BELOW";

export interface CreateAlertRequest {
  alert_type: AlertType;
  target_value: number;
  direction: AlertDirection;
}

export interface AlertResponse {
  id: string;
  stock_id: string;
  alert_type: string;
  target_value: number;
  direction: string;
  status: string;
}
