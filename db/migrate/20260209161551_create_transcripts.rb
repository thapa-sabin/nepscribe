class CreateTranscripts < ActiveRecord::Migration[8.1]
  def change
    create_table :transcripts do |t|
      t.references :recording, null: false, foreign_key: true
      t.text :content

      t.timestamps
    end
  end
end
