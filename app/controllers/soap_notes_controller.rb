class SoapNotesController < ApplicationController
  before_action :set_recording
  before_action :set_step
  before_action :ensure_transcript_exists, only: [:show]

  def show
    @soap_note = @recording.soap_note
  end

  private

  def set_recording
    @recording = Recording.find(params[:recording_id])
  end

  def set_step
    @current_step = "soap"
  end

  def ensure_transcript_exists
    unless @recording.transcript.present?
      redirect_to recording_path(@recording), alert: "You need to complete the transcript first!"
    end
  end
end
