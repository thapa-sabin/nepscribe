require "net/http"
require "uri"
require "json"

class RecordingsController < ApplicationController
  before_action :set_recording, only: [:show]

  def new
    @recording = Recording.new
  end

  def create
    @recording = Recording.new(recording_params)

    if @recording.save
      ProcessRecordingJob.perform_later(@recording.id)
      flash[:notice] = "Recording uploaded successfully. Processing started..."
      redirect_to @recording
    else
      render :new, status: :unprocessable_entity
    end
  end

  def show
    respond_to do |format|
      format.html
      format.json { render json: @recording.slice(:id, :status) } # for polling progress bar
    end
  end

  private

  def set_recording
    @recording = Recording.find(params[:id])
  end

  def recording_params
    params.require(:recording).permit(:audio)
  end
end

