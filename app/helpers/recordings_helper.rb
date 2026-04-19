module RecordingsHelper
  def render_chat_transcript(text)
    return content_tag(:p, "No content available", class: "text-slate-500 italic") if text.blank?

    # Split by newlines to get lines like "SPEAKER_00: Hello world"
    lines = text.split("\n")
    
    content_tag(:div, class: "space-y-4") do
      lines.map do |line|
        if (m = line.match(/^(.*?):\s+(.*)$/))
          raw_label = m[1].strip
          message = m[2].strip
          
          # Heuristic: SPEAKER_00 or "Doctor" is usually the clinician (Primary/Blue)
          is_primary = raw_label.include?("00") || raw_label.downcase.include?("doctor")
          
          # Beautify label: "SPEAKER_00" -> "Speaker 00"
          speaker_label = raw_label.titleize
          
          alignment_class = is_primary ? "justify-end" : "justify-start"
          bubble_class = is_primary ? "bg-blue-600 text-white rounded-br-none" : "bg-white border border-slate-200 text-slate-700 rounded-bl-none"
          label_class = is_primary ? "text-right mr-1" : "text-left ml-1"
          
          content_tag(:div, class: "flex #{alignment_class}") do
            content_tag(:div, class: "max-w-[80%]") do
              concat content_tag(:div, speaker_label, class: "text-xs text-slate-500 mb-1 #{label_class}")
              concat content_tag(:div, message, class: "px-4 py-2.5 rounded-2xl shadow-sm text-sm #{bubble_class}")
            end
          end
        else
          # Fallback for lines that don't match the pattern (e.g. system messages)
          content_tag(:div, line, class: "text-slate-600 text-sm italic text-center")
        end
      end.join.html_safe
    end
  end
end
