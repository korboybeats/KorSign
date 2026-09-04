# Offline checks for publication gates and the direct feed-update connection.
require 'yaml'
root = File.expand_path('..', __dir__)
release = YAML.load_file(File.join(root, '.github/workflows/release.yml'))
feed = YAML.load_file(File.join(root, '.github/workflows/update_repo.yml'))
# Ruby's YAML 1.1 parser reads the GitHub Actions "on" key as true.
events = release.fetch('on', release[true])
raise 'Publication must default off' unless events.fetch('workflow_dispatch').fetch('inputs').fetch('publish').fetch('default') == false
steps = release.fetch('jobs').fetch('build').fetch('steps')
publish = steps.find { |s| s['name'] == 'Create Release' }
raise 'Ungated publication' unless publish.fetch('if') == '${{ inputs.publish }}'
raise 'Wrong publisher' unless publish.fetch('run') == 'sh tools/create_release.sh'
raise 'Validation must precede publication' unless steps.index { |s| s['name'] == 'Validate and stage Main' } < steps.index(publish)
raise 'Checks must precede build' unless steps.index { |s| s['name'] == 'Check release validation' } < steps.index { |s| s['name'] == 'Compile KorSign' }
connection = release.fetch('jobs').fetch('update-feed')
raise 'Feed must follow successful publication' unless connection['needs'] == 'build' && connection['if'] == '${{ inputs.publish }}'
raise 'Wrong feed workflow' unless connection['uses'] == './.github/workflows/update_repo.yml'
raise 'Feed is not callable' unless feed.fetch('on', feed[true]).key?('workflow_call')
raise 'Feed must target default branch' unless feed['jobs']['build']['steps'][0]['with']['ref'] == '${{ github.event.repository.default_branch }}'
[release, feed].each do |workflow|
  workflow.fetch('jobs').each_value do |job|
    job.fetch('steps', []).each do |step|
      next unless step['run']
      IO.popen(['bash', '-n'], 'w') { |io| io.write(step['run']) }
      raise 'Invalid shell syntax' unless $?.success?
    end
  end
end
puts 'PASS: check-only default, publication/validation gates, direct feed dependency, default branch and shell syntax'
