class Transcript < ApplicationRecord
  belongs_to :recording

  validates :content, presence: true
  # diarized_content can be nil if diarization fails
end

