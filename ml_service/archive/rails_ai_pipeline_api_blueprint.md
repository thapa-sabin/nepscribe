# Rails Monolith API Blueprint: Audio -> Diarized Transcript -> SOAP Notes

This document defines a production-friendly API and backend flow for your Rails monolith using SQLite.

## 1) Data Model

Create one main record for each consultation recording.

### Table: `encounters`

- `id`
- `doctor_id` (FK)
- `patient_id` (FK)
- `status` (string enum)
- `transcript_text` (text)
- `diarized_transcript_text` (text)
- `soap_notes` (text)
- `error_message` (text)
- `processing_started_at` (datetime)
- `processing_completed_at` (datetime)
- `created_at`, `updated_at`

Attach audio via Active Storage: `has_one_attached :audio_file`

Suggested status enum:
- `uploaded`
- `queued`
- `transcribing`
- `summarizing`
- `completed`
- `failed`

## 2) API Endpoints

Namespace: `/api/v1`

### POST `/api/v1/encounters`
Create encounter + upload audio.

Request (multipart):
- `patient_id`
- `audio_file`

Response:
```json
{
  "id": 42,
  "status": "uploaded"
}
```

### POST `/api/v1/encounters/:id/process`
Queue AI pipeline.

Response:
```json
{
  "id": 42,
  "status": "queued"
}
```

### GET `/api/v1/encounters/:id`
Fetch encounter details.

Response:
```json
{
  "id": 42,
  "status": "completed",
  "transcript_text": "...",
  "diarized_transcript_text": "SPEAKER_00: ...",
  "soap_notes": "S: ...\\nO: ...\\nA: ...\\nP: ...",
  "error_message": null
}
```

### GET `/api/v1/encounters/:id/status`
Frontend polling endpoint.

Response:
```json
{
  "id": 42,
  "status": "summarizing",
  "error_message": null
}
```

## 3) Rails Routes

```ruby
# config/routes.rb
namespace :api do
  namespace :v1 do
    resources :encounters, only: [:create, :show] do
      member do
        post :process
        get :status
      end
    end
  end
end
```

## 4) Model Skeleton

```ruby
# app/models/encounter.rb
class Encounter < ApplicationRecord
  belongs_to :doctor, class_name: "User"
  belongs_to :patient

  has_one_attached :audio_file

  enum status: {
    uploaded: "uploaded",
    queued: "queued",
    transcribing: "transcribing",
    summarizing: "summarizing",
    completed: "completed",
    failed: "failed"
  }

  validates :status, presence: true
end
```

## 5) Controller Skeleton

```ruby
# app/controllers/api/v1/encounters_controller.rb
class Api::V1::EncountersController < ApplicationController
  before_action :set_encounter, only: [:show, :process, :status]

  def create
    encounter = Encounter.new(
      doctor: current_user,
      patient_id: params[:patient_id],
      status: :uploaded
    )

    encounter.audio_file.attach(params[:audio_file]) if params[:audio_file].present?
    encounter.save!

    render json: { id: encounter.id, status: encounter.status }, status: :created
  end

  def process
    @encounter.update!(status: :queued)
    ProcessEncounterJob.perform_later(@encounter.id)
    render json: { id: @encounter.id, status: @encounter.status }, status: :accepted
  end

  def show
    render json: encounter_payload(@encounter)
  end

  def status
    render json: { id: @encounter.id, status: @encounter.status, error_message: @encounter.error_message }
  end

  private

  def set_encounter
    @encounter = Encounter.find(params[:id])
  end

  def encounter_payload(encounter)
    {
      id: encounter.id,
      status: encounter.status,
      transcript_text: encounter.transcript_text,
      diarized_transcript_text: encounter.diarized_transcript_text,
      soap_notes: encounter.soap_notes,
      error_message: encounter.error_message
    }
  end
end
```

## 6) Background Jobs

Use Active Job + Solid Queue/Sidekiq. Keep orchestration in one job first.

```ruby
# app/jobs/process_encounter_job.rb
class ProcessEncounterJob < ApplicationJob
  queue_as :default

  def perform(encounter_id)
    encounter = Encounter.find(encounter_id)
    encounter.update!(status: :transcribing, processing_started_at: Time.current, error_message: nil)

    transcript_result = MlPipelineClient.new.transcribe_and_diarize(encounter)

    encounter.update!(
      transcript_text: transcript_result.fetch("transcript_text"),
      diarized_transcript_text: transcript_result.fetch("diarized_transcript_text"),
      status: :summarizing
    )

    soap_result = MlPipelineClient.new.generate_soap(encounter.transcript_text)

    encounter.update!(
      soap_notes: soap_result.fetch("soap_notes"),
      status: :completed,
      processing_completed_at: Time.current
    )
  rescue => e
    encounter&.update!(status: :failed, error_message: e.message, processing_completed_at: Time.current)
    raise e
  end
end
```

## 7) ML Service Client

```ruby
# app/services/ml_pipeline_client.rb
class MlPipelineClient
  include HTTParty
  base_uri ENV.fetch("ML_SERVICE_URL")

  def transcribe_and_diarize(encounter)
    file_path = ActiveStorage::Blob.service.send(:path_for, encounter.audio_file.blob.key)

    self.class.post(
      "/v1/transcribe",
      body: {
        audio: File.open(file_path),
        encounter_id: encounter.id
      },
      timeout: 600
    ).parsed_response
  end

  def generate_soap(transcript_text)
    self.class.post(
      "/v1/soap",
      headers: { "Content-Type" => "application/json" },
      body: { transcript_text: transcript_text }.to_json,
      timeout: 300
    ).parsed_response
  end
end
```

## 8) ML Service Contract

### POST `/v1/transcribe`
Input: audio file

Output:
```json
{
  "transcript_text": "full transcript plain text",
  "diarized_transcript_text": "SPEAKER_00: ...\\nSPEAKER_01: ..."
}
```

### POST `/v1/soap`
Input:
```json
{ "transcript_text": "..." }
```

Output:
```json
{ "soap_notes": "S: ...\\nO: ...\\nA: ...\\nP: ..." }
```

## 9) Frontend Polling Pattern (React)

- Call `POST /encounters`
- Call `POST /encounters/:id/process`
- Poll `GET /encounters/:id/status` every 2-3s
- When `status == completed`, call `GET /encounters/:id` and render transcript + SOAP

## 10) SQLite Notes

SQLite is fine for early-stage product and low concurrency.
For production scale, move to PostgreSQL before increasing concurrent background processing.

## 11) Security and Compliance Baseline

- Enforce doctor ownership checks on encounter access.
- Avoid logging transcript/soap payloads in plaintext logs.
- Encrypt backups and storage where possible.
- Add audit events for `create/process/complete/fail`.
