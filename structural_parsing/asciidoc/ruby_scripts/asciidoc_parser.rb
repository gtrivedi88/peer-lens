#!/usr/bin/env ruby

require 'asciidoctor'
require 'json'

def preprocess_header(content)
  """
  Pre-processes the AsciiDoc content to make the header parsing more lenient.
  It removes blank lines within the header block (from the title until the
  first non-header content) before passing it to the main Asciidoctor parser.
  This makes the parser more forgiving to users adding extra newlines.
  """
  lines = content.lines
  processed_lines = []
  state = :seeking_title

  lines.each_with_index do |line, index|
    stripped_line = line.strip

    case state
    when :seeking_title
      # We are looking for the document title to start header processing.
      processed_lines << line
      if stripped_line.start_with?('= ')
        state = :in_header
      elsif !stripped_line.empty? && !stripped_line.start_with?('//')
        # The first significant line is not a title, so there's no header to process.
        # We append the rest of the file and stop processing.
        processed_lines.concat(lines[(index + 1)..-1])
        return processed_lines.join
      end
    when :in_header
      # We are inside the header block. We will strip blank lines here.
      is_attribute = stripped_line.match?(/^:[^:]+:/)
      is_comment = stripped_line.start_with?('//')
      is_blank = stripped_line.empty?

      # Heuristic to detect the start of the document body.
      # This includes section titles, block delimiters, list items, etc.
      is_body_block = stripped_line.start_with?('==', '----', '****', '|===', '++++', '[', '*') || stripped_line.match?(/^\.[\w\s]+/)
      
      # Check if this looks like an author/revision line (common header patterns)
      is_author_line = stripped_line.match?(/^[A-Za-z].*<.*@.*>.*$/) || stripped_line.match?(/^v\d+\.\d+.*\d{4}-\d{2}-\d{2}.*$/)

      if is_blank
        # Forgive the user for adding a blank line by skipping it.
        next
      elsif is_attribute || is_comment
        # This is an attribute or a comment, still part of the header.
        processed_lines << line
      elsif is_author_line
        # This looks like an author or revision line, part of the header.
        processed_lines << line
      elsif is_body_block
        # This line marks the beginning of the body.
        # Stop header processing and switch to copying all subsequent lines as-is.
        state = :in_body
        processed_lines << line
      else
        # Any other content marks the start of the document body.
        # This handles regular paragraphs that come after the header.
        state = :in_body
        processed_lines << line
      end
    when :in_body
      # We are in the main document body, so we preserve all lines, including blanks.
      processed_lines << line
    end
  end

  processed_lines.join
end


def extract_block_info(block, level = 0)
  # Extract content using simple approach
  content = ''
  
  case block.context
  when :list_item
    content = block.respond_to?(:text) && !block.text.nil? ? block.text.to_s : ''
  when :paragraph, :sidebar, :example, :quote, :verse, :literal, :admonition
    if block.respond_to?(:lines) && block.lines && !block.lines.empty?
      content = block.lines.join("\n")
    elsif block.respond_to?(:source) && !block.source.nil?
      content = block.source.to_s
    elsif !block.content.nil?
      content = block.content.to_s
    end
  when :listing
    if block.respond_to?(:source) && !block.source.nil?
      content = block.source.to_s
    elsif block.respond_to?(:lines) && block.lines
      content = block.lines.join("\n")
    end
  when :table
    # For tables, reconstruct content from table structure
    if block.respond_to?(:rows) && block.rows
      content_parts = []
      
      # Add header row if present
      if block.rows.respond_to?(:head) && block.rows.head && !block.rows.head.empty?
        header_row = block.rows.head.first
        if header_row.respond_to?(:each)
          header_cells = header_row.map { |cell| cell.respond_to?(:text) ? cell.text : cell.to_s }
          content_parts << "|#{header_cells.join(" |")} |"
        end
      end
      
      # Add body rows if present
      if block.rows.respond_to?(:body) && block.rows.body
        block.rows.body.each do |row|
          if row.respond_to?(:each)
            row_cells = row.map { |cell| cell.respond_to?(:text) ? cell.text : cell.to_s }
            content_parts << "|#{row_cells.join(" |")} |"
          end
        end
      end
      
      content = content_parts.join("\n")
    else
      # Fallback
      content = ''
    end
  else
    if block.respond_to?(:source) && !block.source.nil?
      content = block.source.to_s
    elsif block.respond_to?(:lines) && block.lines && !block.lines.empty?
      content = block.lines.join("\n")
    elsif !block.content.nil?
      content = block.content.to_s
    elsif block.respond_to?(:text) && !block.text.nil?
      content = block.text.to_s
    end
  end
  
  # Clean up HTML tags (except for code blocks)
  unless [:listing, :literal].include?(block.context)
    if content.include?('<') && content.include?('>')
      content = content.gsub(/<[^>]+>/, '').gsub(/\s+/, ' ').strip
    end
  end
  
  # Determine block level
  block_level = level
  if block.context == :section
    block_level = block.level if block.respond_to?(:level)
  elsif block.context == :heading
    if block.respond_to?(:level)
      block_level = block.level
    elsif block.attributes && block.attributes['level']
      block_level = block.attributes['level'].to_i
    end
  end

  block_info = {
    'context' => block.context.to_s,
    'content_model' => block.content_model.to_s,
    'content' => content,
    'level' => block_level,
    'style' => block.style,
    'title' => block.title,
    'id' => block.id,
    'attributes' => block.attributes.to_h,
    'raw_content' => content
  }
  
  # Add source location if available
  if block.source_location
    block_info['source_location'] = {
      'file' => block.source_location.file,
      'lineno' => block.source_location.lineno,
      'path' => block.source_location.path
    }
  end
  
  # Get lines for content blocks
  if block.respond_to?(:lines) && block.lines
    block_info['lines'] = block.lines
  elsif block.respond_to?(:source) && block.source
    if block.source.is_a?(Array)
      block_info['lines'] = block.source
    else
      block_info['lines'] = [block.source.to_s]
    end
  end
  
  # Extract children blocks
  children = []
  
  # Special handling for table blocks - extract rows and cells as children
  if block.context == :table && block.respond_to?(:rows) && block.rows
    # Add header row as a child if present
    if block.rows.respond_to?(:head) && block.rows.head && !block.rows.head.empty?
      header_row = block.rows.head.first
      if header_row.respond_to?(:each)
        row_info = {
          'context' => 'table_row',
          'content_model' => 'compound',
          'content' => '',
          'level' => level + 1,
          'style' => 'header',
          'title' => nil,
          'id' => nil,
          'attributes' => { 'role' => 'header' },
          'children' => []
        }
        
        # Add cells as children of the row
        header_row.each_with_index do |cell, cell_index|
          cell_content = cell.respond_to?(:text) ? cell.text : cell.to_s
          cell_info = {
            'context' => 'table_cell',
            'content_model' => 'simple',
            'content' => cell_content,
            'level' => level + 2,
            'style' => nil,
            'title' => nil,
            'id' => nil,
            'attributes' => { 'column' => cell_index + 1, 'role' => 'header' },
            'children' => []
          }
          row_info['children'] << cell_info
        end
        
        children << row_info
      end
    end
    
    # Add body rows as children if present
    if block.rows.respond_to?(:body) && block.rows.body
      block.rows.body.each_with_index do |row, row_index|
        if row.respond_to?(:each)
          row_info = {
            'context' => 'table_row',
            'content_model' => 'compound',
            'content' => '',
            'level' => level + 1,
            'style' => 'body',
            'title' => nil,
            'id' => nil,
            'attributes' => { 'row' => row_index + 1 },
            'children' => []
          }
          
          # Add cells as children of the row
          row.each_with_index do |cell, cell_index|
            cell_content = cell.respond_to?(:text) ? cell.text : cell.to_s
            cell_info = {
              'context' => 'table_cell',
              'content_model' => 'simple',
              'content' => cell_content,
              'level' => level + 2,
              'style' => nil,
              'title' => nil,
              'id' => nil,
              'attributes' => { 'column' => cell_index + 1, 'row' => row_index + 1 },
              'children' => []
            }
            row_info['children'] << cell_info
          end
          
          children << row_info
        end
      end
    end
  end
  
  # Regular children blocks (for non-table blocks or additional table children)
  if block.respond_to?(:blocks) && block.blocks
    block.blocks.each do |child_block|
      children << extract_block_info(child_block, level + 1)
    end
  end
  
  block_info['children'] = children
  
  # Handle special block types
  case block.context
  when :admonition
    block_info['admonition_name'] = block.attr('name') || block.attr('style') || 'NOTE'
  when :list_item
    block_info['text'] = block.text if block.respond_to?(:text)
    block_info['marker'] = block.marker if block.respond_to?(:marker)
  when :listing, :literal
    block_info['language'] = block.attr('language') if block.attr('language')
    block_info['linenums'] = block.attr('linenums') if block.attr('linenums')
  end
  
  block_info
end

def parse_asciidoc(content)
  begin
    # Pre-process the content to handle blank lines in the header forgivingly
    processed_content = preprocess_header(content)

    # Parse the document - AsciiDoctor handles header/body separation automatically
    doc = Asciidoctor.load(processed_content, 
      sourcemap: true, 
      safe: :unsafe,
      parse_header_only: false,
      standalone: false)
    
    # Extract document structure
    result = {
      'title' => doc.doctitle,
      'attributes' => doc.attributes.to_h,
      'blocks' => []
    }
    
    # Add document title as a heading block if it exists
    if doc.doctitle && doc.header?
      title_block = {
        'context' => 'heading',
        'content_model' => 'empty',
        'content' => doc.doctitle,
        'level' => 0,
        'style' => nil,
        'title' => nil,
        'id' => nil,
        'attributes' => {},
        'source_location' => {
          'file' => '<content>',
          'lineno' => 1,
          'path' => '<content>'
        },
        'lines' => ["= #{doc.doctitle}"],
        'children' => []
      }
      result['blocks'] << title_block
    end
    
    # Extract blocks from the document body only (AsciiDoctor separates header automatically)
    doc.blocks.each do |block|
      # AsciiDoctor should already exclude header content from doc.blocks
      # Only skip blocks that are clearly empty or whitespace-only
      next if block_is_empty_or_whitespace(block)
      
      block_info = extract_block_info(block)
      result['blocks'] << block_info if block_info
    end
    
    {
      'success' => true,
      'data' => result
    }
  rescue => e
    {
      'success' => false,
      'error' => e.message
    }
  end
end

def block_is_empty_or_whitespace(block)
  """Check if a block is empty or contains only whitespace."""
  
  # Trust AsciiDoctor for most block types
  return false unless block.context == :paragraph
  
  # For paragraphs, check if content is effectively empty
  content = block.content.to_s.strip
  return true if content.empty?
  
  # Check if it's just whitespace or very short non-meaningful content
  return true if content.length <= 3 && content.match?(/^[\s\-\.\:]*$/)
  
  false
end

# Main execution
if __FILE__ == $0
  if ARGV.length != 2
    STDERR.puts "Usage: ruby asciidoc_parser.rb input_file output_file"
    exit 1
  end
  
  input_file = ARGV[0]
  output_file = ARGV[1]
  
  begin
    content = File.read(input_file)
    result = parse_asciidoc(content)
    File.write(output_file, JSON.generate(result))
  rescue => e
    error_result = {
      'success' => false,
      'error' => e.message
    }
    File.write(output_file, JSON.generate(error_result))
    exit 1
  end
end
