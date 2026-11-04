import { Link } from "react-router-dom";
import type { PricingModelStatus } from "../../lib/adminApi";
import {
  formatDays,
  formatPlainPct,
  modelQuality,
  modelStatusSummary,
  topFactors,
  trainingDataLine,
} from "../../lib/adminPricing";
import { IconAlert } from "./AdminIcons";
import LoadState from "./LoadState";
import { Chip } from "./StatusChip";

type Props = {
  model: PricingModelStatus | null;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  /** Opens the retrain confirm dialog. */
  onRetrain: () => void;
  retraining: boolean;
};

function ModelDetails({ model }: { model: PricingModelStatus }) {
  const status = modelStatusSummary(model);
  const quality = modelQuality(model.metrics);
  const factors = topFactors(model.feature_importance, 5);
  const dataLine = trainingDataLine(model.data);
  const trainable = Number(model.data?.trainable ?? model.occupancy_rows) || 0;
  const enough = trainable >= (Number(model.min_rows_required) || 0);

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone={status.chip.tone}>{status.chip.label}</Chip>
          <p className="admin-fg min-w-0 text-sm font-medium">{status.headline}</p>
        </div>
        {status.detail ? <p className="admin-faint mt-1 text-xs">{status.detail}</p> : null}
      </div>

      {model.last_error ? (
        <p className="admin-alert admin-alert--warning flex items-start gap-2" role="status">
          <span className="mt-0.5 shrink-0" aria-hidden>
            <IconAlert />
          </span>
          <span className="min-w-0 break-words">Last problem: {model.last_error}</span>
        </p>
      ) : null}

      {status.state !== "none" ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="min-w-0">
            <p className="admin-label">How accurate</p>
            {quality ? (
              <div className="space-y-0.5">
                {quality.error ? <p className="admin-fg admin-num text-sm">{quality.error}</p> : null}
                {quality.improvement ? (
                  <p className={`admin-num text-sm ${quality.better ? "admin-success-text" : "admin-warning-text"}`}>
                    {quality.improvement}
                  </p>
                ) : null}
                <p className="admin-faint pt-1 text-[11px]">
                  Checked on the most recent days, which the model didn't see while learning.
                </p>
              </div>
            ) : (
              <p className="admin-muted text-xs">No accuracy numbers for this model yet. Retrain to measure it.</p>
            )}
          </div>

          <div className="min-w-0">
            <p className="admin-label">What drives demand</p>
            {factors.length ? (
              <ul className="space-y-2" aria-label="What drives demand, biggest factor first">
                {factors.map((f) => (
                  <li key={f.feature} className="min-w-0">
                    <div className="flex items-baseline justify-between gap-3 text-xs">
                      <span className="admin-fg min-w-0 break-words">{f.label}</span>
                      <span className="admin-muted admin-num shrink-0">{formatPlainPct(f.share * 100)}</span>
                    </div>
                    <div className="admin-bar-track mt-1" aria-hidden>
                      <div className="admin-bar-fill" style={{ width: `${f.widthPct}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="admin-muted text-xs">The main factors appear here after training.</p>
            )}
          </div>
        </div>
      ) : null}

      <div className="admin-divider pt-3">
        {dataLine ? (
          <p className="admin-muted admin-num text-xs">{dataLine}</p>
        ) : (
          <p className="admin-muted admin-num text-xs">{formatDays(model.occupancy_rows)} of occupancy available</p>
        )}
        <p className="admin-faint mt-0.5 text-[11px]">
          App-generated days are filler the app creates when a client checks dates. They never train the model.
        </p>
        {!enough ? (
          <p className="admin-alert admin-alert--warning mt-3">
            The model needs at least {formatDays(model.min_rows_required)} of real history. Import more on the{" "}
            <Link to="/admin/occupancy" className="admin-link">
              Occupancy page
            </Link>
            , then retrain.
          </p>
        ) : null}
      </div>
    </div>
  );
}

/** Model card on the Pricing page: status, accuracy, top factors and training data, in plain words. */
export default function PricingModelCard({ model, loading, error, onRetry, onRetrain, retraining }: Props) {
  return (
    <section className="admin-card p-4" aria-labelledby="pr-model">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 id="pr-model" className="admin-section-title">
          Pricing model
        </h3>
        <button type="button" className="studio-btn-secondary" disabled={!model || retraining} onClick={onRetrain}>
          {retraining ? "Retraining…" : "Retrain model"}
        </button>
      </div>
      {!model ? (
        <LoadState
          loading={loading}
          error={error}
          onRetry={onRetry}
          errorTitle="We couldn't load the model status."
          compact
        />
      ) : (
        <ModelDetails model={model} />
      )}
    </section>
  );
}
