class Recording < ApplicationRecord
  has_one_attached :audio
  has_one :transcript
  has_one :summary
end
