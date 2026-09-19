import { FormEvent, useState } from "react";

import type { AlertDirection, AlertType } from "../../models/alerts";
import { createAlert } from "../../services/alertService";

interface Props {
  stockId: string;
}

export default function StockAlertPanel({ stockId }: Props): JSX.Element {
  const [alertType, setAlertType] = useState<AlertType>("ABSOLUTE");
  const [direction, setDirection] = useState<AlertDirection>("ABOVE");
  const [targetValue, setTargetValue] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setSuccessMsg("");
    setErrorMsg("");

    const parsed = parseFloat(targetValue);
    if (isNaN(parsed) || parsed <= 0) {
      setErrorMsg("Enter a positive target value.");
      return;
    }

    setSubmitting(true);
    try {
      await createAlert(stockId, {
        alert_type: alertType,
        target_value: parsed,
        direction,
      });
      setSuccessMsg(
        `Alert set: notify me when price is ${direction.toLowerCase()} ` +
          (alertType === "ABSOLUTE" ? `$${parsed.toFixed(2)}` : `${parsed}%`),
      );
      setTargetValue("");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      setErrorMsg(
        typeof detail === "string" ? detail : "Failed to create alert.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const placeholder =
    alertType === "ABSOLUTE" ? "e.g. 200.00  (price in $)" : "e.g. 5  (% change)";

  return (
    <section className="dashboard-panel stock-alert-panel">
      <h2>Set Price Alert</h2>
      <p className="stock-alert-hint">
        Get notified by email and in-app banner when the condition is met.
      </p>

      <form className="stock-alert-form" onSubmit={(e) => void handleSubmit(e)}>
        <div className="stock-alert-row">
          <span className="stock-alert-label">Alert type</span>
          <div className="stock-alert-toggle" role="group">
            {(["ABSOLUTE", "PERCENT"] as AlertType[]).map((t) => (
              <button
                key={t}
                type="button"
                className={
                  alertType === t
                    ? "stock-alert-toggle-btn stock-alert-toggle-btn-active"
                    : "stock-alert-toggle-btn"
                }
                onClick={() => {
                  setAlertType(t);
                  setTargetValue("");
                  setSuccessMsg("");
                  setErrorMsg("");
                }}
              >
                {t === "ABSOLUTE" ? "Fixed price ($)" : "Daily % change"}
              </button>
            ))}
          </div>
        </div>

        <div className="stock-alert-row">
          <span className="stock-alert-label">Direction</span>
          <div className="stock-alert-toggle" role="group">
            {(["ABOVE", "BELOW"] as AlertDirection[]).map((d) => (
              <button
                key={d}
                type="button"
                className={
                  direction === d
                    ? "stock-alert-toggle-btn stock-alert-toggle-btn-active"
                    : "stock-alert-toggle-btn"
                }
                onClick={() => {
                  setDirection(d);
                  setSuccessMsg("");
                  setErrorMsg("");
                }}
              >
                {d === "ABOVE" ? "Goes above" : "Falls below"}
              </button>
            ))}
          </div>
        </div>

        <div className="form-group stock-alert-value-group">
          <label htmlFor="alert-target">
            Target value{alertType === "ABSOLUTE" ? " ($)" : " (%)"}
          </label>
          <input
            id="alert-target"
            type="number"
            min="0"
            step="any"
            placeholder={placeholder}
            value={targetValue}
            onChange={(e) => {
              setTargetValue(e.target.value);
              setSuccessMsg("");
              setErrorMsg("");
            }}
            disabled={submitting}
          />
        </div>

        {errorMsg && <p className="control-error">{errorMsg}</p>}
        {successMsg && <p className="stock-alert-success">{successMsg}</p>}

        <button
          type="submit"
          className="btn-solid stock-alert-submit"
          disabled={submitting || targetValue === ""}
        >
          {submitting ? "Setting alert..." : "Set alert"}
        </button>
      </form>
    </section>
  );
}
