require "net/http"
require "uri"
require "json"

class ProcessRecordingJob < ApplicationJob
  queue_as :default
  retry_on StandardError, wait: 5.seconds, attempts: 3

  def perform(recording_id)
    recording = Recording.find(recording_id)
    return unless recording.audio.attached?

    # mark as processing
    recording.update!(status: "processing")

    # send audio to FastAPI pipeline
    uri = URI("http://localhost:8000/v1/pipeline")
    request = Net::HTTP::Post.new(uri)

    file_data = recording.audio.download
    request.set_form(
      [["audio_file", file_data,
        { filename: recording.audio.filename.to_s, content_type: recording.audio.content_type }
      ]],
      "multipart/form-data"
    )

    http = Net::HTTP.new(uri.hostname, uri.port)
    http.open_timeout  = 10
    http.read_timeout  = 600
    http.write_timeout = 600

    response = http.start { |h| h.request(request) }

    unless response.is_a?(Net::HTTPSuccess)
      raise "FastAPI request failed: #{response.body}"
    end

    data = JSON.parse(response.body)

    # 1️⃣ Create or update Transcript
    transcript = recording.transcript || recording.build_transcript
    transcript.update!(
      content: data["transcript_text"],
      diarized_content: data["diarized_transcript_text"]
    )

    # 2️⃣ Create or update SOAP note
    soap_sections = data["soap"] || {}

    # fallback parser if structured sections missing
    if soap_sections.blank? || soap_sections.values.all?(&:blank?)
      s, o, a, p = parse_soap(data["soap_text"])
      soap_sections = {
        "subjective" => s.presence,
        "objective" => o.presence,
        "assessment" => a.presence,
        "plan" => p.presence
      }
    end

    if soap_sections.any? { |_, v| v.present? }
      soap_note = recording.soap_note || recording.build_soap_note
      soap_note.update!(
        subjective: soap_sections["subjective"].presence,
        objective: soap_sections["objective"].presence,
        assessment: soap_sections["assessment"].presence,
        plan: soap_sections["plan"].presence
      )
    end

    # mark recording as completed
    recording.update!(status: "completed", processed_at: Time.current)

  rescue => e
    recording.update!(status: "failed") if recording
    Rails.logger.error("Transcription error for Recording ##{recording_id}: #{e.message}")
    raise e
  end

  private

  # fallback SOAP parser (crude, line-based)
  def parse_soap(soap_text)
    s = o = a = p = ""
    return [s, o, a, p] if soap_text.blank?

    current_section = nil
    soap_text.lines.each do |line|
      case line.strip
      when /\A(S|Subjective)[:\-]/i
        current_section = :s
        s += line.sub(/.*[:\-]\s*/, "") + "\n"
      when /\A(O|Objective)[:\-]/i
        current_section = :o
        o += line.sub(/.*[:\-]\s*/, "") + "\n"
      when /\A(A|Assessment)[:\-]/i
        current_section = :a
        a += line.sub(/.*[:\-]\s*/, "") + "\n"
      when /\A(P|Plan)[:\-]/i
        current_section = :p
        p += line.sub(/.*[:\-]\s*/, "") + "\n"
      else
        case current_section
        when :s then s += line + "\n"
        when :o then o += line + "\n"
        when :a then a += line + "\n"
        when :p then p += line + "\n"
        end
      end
    end

    [s.strip, o.strip, a.strip, p.strip]
  end
end

