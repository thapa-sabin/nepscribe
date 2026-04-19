class AddTranscriptFieldsToRecordings < ActiveRecord::Migration[8.1]
  def change
    add_column :recordings, :transcript, :text
    add_column :recordings, :diarized_transcript, :text
  end
end
