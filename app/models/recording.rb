class Recording < ApplicationRecord
  has_one_attached :audio

  has_one :transcript, dependent: :destroy
  has_one :soap_note, dependent: :destroy

  validates :status, inclusion: { in: %w[pending processing completed failed] }, allow_nil: true

  after_initialize :set_default_status, if: :new_record?

  private

  def set_default_status
    self.status ||= "pending"
  end
end

