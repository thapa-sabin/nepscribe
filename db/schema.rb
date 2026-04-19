# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_02_17_150232) do
  create_table "active_storage_attachments", force: :cascade do |t|
    t.bigint "blob_id", null: false
    t.datetime "created_at", null: false
    t.string "name", null: false
    t.bigint "record_id", null: false
    t.string "record_type", null: false
    t.index ["blob_id"], name: "index_active_storage_attachments_on_blob_id"
    t.index ["record_type", "record_id", "name", "blob_id"], name: "index_active_storage_attachments_uniqueness", unique: true
  end

  create_table "active_storage_blobs", force: :cascade do |t|
    t.bigint "byte_size", null: false
    t.string "checksum"
    t.string "content_type"
    t.datetime "created_at", null: false
    t.string "filename", null: false
    t.string "key", null: false
    t.text "metadata"
    t.string "service_name", null: false
    t.index ["key"], name: "index_active_storage_blobs_on_key", unique: true
  end

  create_table "active_storage_variant_records", force: :cascade do |t|
    t.bigint "blob_id", null: false
    t.string "variation_digest", null: false
    t.index ["blob_id", "variation_digest"], name: "index_active_storage_variant_records_uniqueness", unique: true
  end

  create_table "recordings", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.text "diarized_transcript"
    t.datetime "processed_at"
    t.text "soap_text"
    t.string "status"
    t.string "title"
    t.text "transcript"
    t.datetime "updated_at", null: false
  end

  create_table "soap_notes", force: :cascade do |t|
    t.text "assessment"
    t.datetime "created_at", null: false
    t.text "objective"
    t.text "plan"
    t.integer "recording_id", null: false
    t.text "subjective"
    t.datetime "updated_at", null: false
    t.index ["recording_id"], name: "index_soap_notes_on_recording_id"
  end

  create_table "solid_queue_processes", force: :cascade do |t|
    t.text "arguments"
    t.datetime "created_at", null: false
    t.string "handler"
    t.integer "priority", default: 0
    t.string "queue"
    t.datetime "run_at"
    t.datetime "updated_at", null: false
  end

  create_table "summaries", force: :cascade do |t|
    t.text "content"
    t.datetime "created_at", null: false
    t.integer "recording_id", null: false
    t.datetime "updated_at", null: false
    t.index ["recording_id"], name: "index_summaries_on_recording_id"
  end

  create_table "transcripts", force: :cascade do |t|
    t.text "content"
    t.datetime "created_at", null: false
    t.text "diarized_content"
    t.integer "recording_id", null: false
    t.datetime "updated_at", null: false
    t.index ["recording_id"], name: "index_transcripts_on_recording_id"
  end

  create_table "users", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "email"
    t.datetime "updated_at", null: false
  end

  add_foreign_key "active_storage_attachments", "active_storage_blobs", column: "blob_id"
  add_foreign_key "active_storage_variant_records", "active_storage_blobs", column: "blob_id"
  add_foreign_key "soap_notes", "recordings"
  add_foreign_key "summaries", "recordings"
  add_foreign_key "transcripts", "recordings"
end
