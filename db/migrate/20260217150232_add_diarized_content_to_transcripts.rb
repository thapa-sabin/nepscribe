class AddDiarizedContentToTranscripts < ActiveRecord::Migration[8.1]
  def change
    add_column :transcripts, :diarized_content, :text
  end
end
