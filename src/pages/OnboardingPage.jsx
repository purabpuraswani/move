import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { completeProfile } from "../services/profile";
import { createReport, extractReport } from "../services/reports";

import "./OnboardingPage.css";


// The health-background questions, with a hint about which documents are
// worth attaching when the answer is yes.
const HEALTH_CONDITIONS = [
  ["diabetes", "Diabetes", "HbA1c or blood sugar reports"],
  ["hypertension", "Hypertension", "BP readings or prescriptions"],
  ["heart_condition", "Heart condition", "ECG, echo or cardiologist notes"],
  ["previous_injury", "Previous injury", "X-ray, MRI or discharge summary"],
  ["joint_pain", "Current joint pain", "Scans or physio notes"],
  ["back_neck_pain", "Back / neck pain", "Scans or physio notes"]
];

const CONDITION_LABELS = Object.fromEntries(
  HEALTH_CONDITIONS.map(([name, label]) => [name, label])
);

const MAX_FILES_PER_GROUP = 5;
const MAX_FILE_MB = 10;
const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];


// Check newly picked files against the per-group limits. Returns the files
// that can be kept and, if any were turned away, a sentence saying why.
function acceptFiles(existing, picked) {

  const accepted = [...existing];
  const problems = [];

  for (const file of picked) {

    const name = file.name.toLowerCase();

    if (!ALLOWED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
      problems.push(`${file.name} is not a PDF, JPG or PNG`);
    } else if (file.size > MAX_FILE_MB * 1024 * 1024) {
      problems.push(`${file.name} is larger than ${MAX_FILE_MB} MB`);
    } else if (accepted.length >= MAX_FILES_PER_GROUP) {
      problems.push(`only ${MAX_FILES_PER_GROUP} files can be added here`);
      break;
    } else {
      accepted.push(file);
    }

  }

  return {
    files: accepted,
    error: problems.length > 0 ? `Not added: ${problems.join("; ")}.` : ""
  };

}


function OnboardingPage() {

  const navigate = useNavigate();

  const [step, setStep] = useState(1);

  const [form, setForm] = useState({

    age: "",
    sex: "",

    height_cm: "",
    weight_kg: "",

    daily_sitting_hours: "",
    daily_screen_hours: "",

    sleep_hours: "",
    sleep_quality: "",

    daily_steps: "",

    exercise_days: "",
    exercise_minutes: "",

    work_type: "",

    diabetes: "",
    hypertension: "",
    heart_condition: "",

    previous_injury: "",
    joint_pain: "",
    back_neck_pain: "",

    other_conditions: ""
  });


  // Step 4's general documents, not tied to one condition.
  const [documents, setDocuments] = useState([]);

  // Files attached to a "yes" answer, keyed by condition name.
  const [conditionFiles, setConditionFiles] = useState({});

  // Messages for files that were turned away, keyed by condition name, or
  // "other" for step 4.
  const [fileErrors, setFileErrors] = useState({});

  // Once the profile is saved, a retry only re-sends the uploads that failed.
  const [profileSaved, setProfileSaved] = useState(false);

  const [failedUploads, setFailedUploads] = useState([]);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const formRef = useRef(null);


  // Which step asks for each field the backend requires. Only the current
  // step's inputs are rendered, so the browser's `required` check can't see
  // fields on earlier steps; this lets submit send the user back to them.
  const REQUIRED_FIELDS = {
    1: ["age", "sex", "height_cm", "weight_kg"],
    2: [
      "daily_sitting_hours",
      "daily_screen_hours",
      "sleep_hours",
      "sleep_quality",
      "daily_steps",
      "exercise_days",
      "exercise_minutes",
      "work_type"
    ],
    3: [
      "diabetes",
      "hypertension",
      "heart_condition",
      "previous_injury",
      "joint_pain",
      "back_neck_pain"
    ]
  };


  function firstIncompleteStep() {

    for (const [stepNumber, fields] of Object.entries(REQUIRED_FIELDS)) {

      if (fields.some((field) => String(form[field] ?? "").trim() === "")) {
        return Number(stepNumber);
      }

    }

    return null;

  }


  function handleChange(e) {

    const { name, value } = e.target;

    const attached = conditionFiles[name] || [];

    // Moving a condition off "yes" drops the files attached to it, so ask
    // first rather than losing them silently.
    if (value !== "yes" && attached.length > 0) {

      const count = attached.length;

      if (
        !window.confirm(
          `Remove ${count} attached file${count === 1 ? "" : "s"}?`
        )
      ) {
        return;
      }

      setConditionFiles({ ...conditionFiles, [name]: [] });
      setFileErrors({ ...fileErrors, [name]: "" });

    }

    setForm({
      ...form,
      [name]: value
    });

  }


  function handleConditionFiles(name, e) {

    const { files, error } = acceptFiles(
      conditionFiles[name] || [],
      Array.from(e.target.files)
    );

    // Cleared so picking the same file again still fires onChange.
    e.target.value = "";

    setConditionFiles({ ...conditionFiles, [name]: files });
    setFileErrors({ ...fileErrors, [name]: error });

  }


  function removeConditionFile(name, index) {

    setConditionFiles({
      ...conditionFiles,
      [name]: conditionFiles[name].filter((_, i) => i !== index)
    });

    setFileErrors({ ...fileErrors, [name]: "" });

  }


  function handleDocuments(e) {

    const { files, error } = acceptFiles(
      documents,
      Array.from(e.target.files)
    );

    e.target.value = "";

    setDocuments(files);
    setFileErrors({ ...fileErrors, other: error });

  }


  function removeDocument(index) {

    setDocuments(documents.filter((_, i) => i !== index));

    setFileErrors({ ...fileErrors, other: "" });

  }


  // Every file to send to the report pipeline, tagged with what it is about.
  // Files on a condition no longer answered "yes" are removed in
  // handleChange, but are filtered here as well so none can slip through.
  function pendingUploads() {

    const tagged = HEALTH_CONDITIONS.flatMap(([name]) =>
      form[name] === "yes"
        ? (conditionFiles[name] || []).map((file) => ({ file, condition: name }))
        : []
    );

    return [
      ...tagged,
      ...documents.map((file) => ({ file, condition: "other" }))
    ];

  }


  // Upload each file as its own report. Failures are returned rather than
  // thrown, so one bad file does not undo the rest.
  async function uploadReports(uploads) {

    const results = await Promise.allSettled(
      uploads.map(({ file, condition }) => {

        const label = CONDITION_LABELS[condition] || "Other document";

        return createReport({
          file,
          condition,
          title: `${label}: ${file.name}`.slice(0, 160)
        });

      })
    );

    const uploaded = [];
    const failed = [];

    results.forEach((result, index) => {

      if (result.status === "fulfilled") {
        uploaded.push(result.value.report.id);
      } else {
        failed.push({ ...uploads[index], error: result.reason?.message });
      }

    });

    // Reading starts in the background, one report at a time, and is not
    // waited for: the user reviews the values later from the dashboard. If
    // automatic reading is not set up the report stays "uploaded", which the
    // reports page already explains.
    uploaded.reduce(
      (chain, reportId) =>
        chain.then(() => extractReport(reportId).catch(() => {})),
      Promise.resolve()
    );

    return failed;

  }


  function renderFileList(files, onRemove) {

    if (files.length === 0) return null;

    return (

      <div className="selected-documents">

        {files.map((file, index) => (

          <div
            className="selected-document"
            key={`${file.name}-${index}`}
          >

            <span>📄</span>

            <div>

              <strong>
                {file.name}
              </strong>

              <small>
                {(file.size / 1024).toFixed(1)} KB
              </small>

            </div>

            <button
              type="button"
              className="remove-document"
              onClick={() => onRemove(index)}
              aria-label={`Remove ${file.name}`}
            >
              ×
            </button>

          </div>

        ))}

      </div>

    );

  }


  function nextStep() {

    setError("");

    // Check the fields on this step (min/max, required) before moving on.
    if (formRef.current && !formRef.current.reportValidity()) {
      return;
    }

    if (step < 4) {
      setStep(step + 1);
    }

  }


  function previousStep() {

    setError("");

    if (step > 1) {
      setStep(step - 1);
    }

  }


  async function handleSubmit(e) {

    e.preventDefault();

    setError("");

    const incompleteStep = firstIncompleteStep();

    if (incompleteStep !== null) {
      setStep(incompleteStep);
      setError(
        `Please complete all required fields in step ${incompleteStep} before finishing.`
      );
      return;
    }

    setLoading(true);


    try {

      if (!profileSaved) {

        // The backend identifies the user from the auth token, so no user id
        // is sent with the form. Documents go to the report pipeline below
        // rather than with the profile.
        const formData = new FormData();


        Object.entries(form).forEach(
          ([key, value]) => {

            formData.append(
              key,
              value
            );

          }
        );


        await completeProfile(
          formData
        );

        setProfileSaved(true);

      }


      const failed = await uploadReports(
        profileSaved ? failedUploads : pendingUploads()
      );

      setFailedUploads(failed);

      if (failed.length > 0) {
        setStep(4);
        return;
      }


      navigate("/dashboard");

    } catch (err) {

      setError(err.message);

    } finally {

      setLoading(false);

    }

  }


  return (

    <div className="onboarding-page">

      <div className="onboarding-container">


        {/* Progress */}

        <div className="onboarding-progress">

          <div
            className={
              step >= 1
                ? "progress-step active"
                : "progress-step"
            }
          >
            01
          </div>

          <div className="progress-line" />

          <div
            className={
              step >= 2
                ? "progress-step active"
                : "progress-step"
            }
          >
            02
          </div>

          <div className="progress-line" />

          <div
            className={
              step >= 3
                ? "progress-step active"
                : "progress-step"
            }
          >
            03
          </div>

          <div className="progress-line" />

          <div
            className={
              step >= 4
                ? "progress-step active"
                : "progress-step"
            }
          >
            04
          </div>

        </div>


        {/* Header */}

        <div className="onboarding-header">

          <span className="section-tag">
            YOUR WELLNESS PROFILE
          </span>

          <h1>
            Let's understand
            <span> you better.</span>
          </h1>

          <p>
            This information helps MoveWell AI
            personalize your movement and wellness
            recommendations.
          </p>

        </div>


        {/* Form */}

        <form
          ref={formRef}
          onSubmit={handleSubmit}
          className="onboarding-form"
        >


          {/* STEP 1 */}

          {step === 1 && (

            <div className="form-step">

              <h2>Basic information</h2>

              <p className="step-description">
                Tell us a little about yourself.
              </p>


              <div className="form-grid">

                <div className="input-group">

                  <label>Age</label>

                  <input
                    type="number"
                    name="age"
                    min="13"
                    max="120"
                    value={form.age}
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>Sex</label>

                  <select
                    name="sex"
                    value={form.sex}
                    onChange={handleChange}
                    required
                  >

                    <option value="">
                      Select
                    </option>

                    <option value="female">
                      Female
                    </option>

                    <option value="male">
                      Male
                    </option>

                    <option value="other">
                      Other
                    </option>

                    <option value="prefer_not_to_say">
                      Prefer not to say
                    </option>

                  </select>

                </div>


                <div className="input-group">

                  <label>
                    Height (cm)
                  </label>

                  <input
                    type="number"
                    name="height_cm"
                    value={form.height_cm}
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Weight (kg)
                  </label>

                  <input
                    type="number"
                    step="0.1"
                    name="weight_kg"
                    value={form.weight_kg}
                    onChange={handleChange}
                    required
                  />

                </div>

              </div>

            </div>

          )}


          {/* STEP 2 */}

          {step === 2 && (

            <div className="form-step">

              <h2>Lifestyle</h2>

              <p className="step-description">
                Help us understand your daily routine.
              </p>


              <div className="form-grid">


                <div className="input-group">

                  <label>
                    Daily sitting hours
                  </label>

                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    max="24"
                    name="daily_sitting_hours"
                    value={
                      form.daily_sitting_hours
                    }
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Daily screen time (hours)
                  </label>

                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    max="24"
                    name="daily_screen_hours"
                    value={
                      form.daily_screen_hours
                    }
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Sleep duration (hours)
                  </label>

                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    max="24"
                    name="sleep_hours"
                    value={form.sleep_hours}
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Sleep quality
                  </label>

                  <select
                    name="sleep_quality"
                    value={form.sleep_quality}
                    onChange={handleChange}
                    required
                  >

                    <option value="">
                      Select
                    </option>

                    <option value="poor">
                      Poor
                    </option>

                    <option value="average">
                      Average
                    </option>

                    <option value="good">
                      Good
                    </option>

                  </select>

                </div>


                <div className="input-group">

                  <label>
                    Daily steps
                  </label>

                  <input
                    type="number"
                    name="daily_steps"
                    min="0"
                    value={form.daily_steps}
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Exercise days / week
                  </label>

                  <input
                    type="number"
                    name="exercise_days"
                    min="0"
                    max="7"
                    value={form.exercise_days}
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Exercise duration (min)
                  </label>

                  <input
                    type="number"
                    name="exercise_minutes"
                    min="0"
                    value={form.exercise_minutes}
                    onChange={handleChange}
                    required
                  />

                </div>


                <div className="input-group">

                  <label>
                    Work type
                  </label>

                  <select
                    name="work_type"
                    value={form.work_type}
                    onChange={handleChange}
                    required
                  >

                    <option value="">
                      Select
                    </option>

                    <option value="mostly_sitting">
                      Mostly sitting
                    </option>

                    <option value="mixed">
                      Mixed
                    </option>

                    <option value="mostly_standing">
                      Mostly standing
                    </option>

                    <option value="physically_demanding">
                      Physically demanding
                    </option>

                  </select>

                </div>

              </div>

            </div>

          )}


          {/* STEP 3 */}

          {step === 3 && (

            <div className="form-step">

              <h2>Health background</h2>

              <p className="step-description">
                This information is optional and helps
                us personalize your experience.
              </p>


              <div className="health-options">

                {HEALTH_CONDITIONS.map(([name, label, hint]) => (

                  <div
                    className={
                      form[name] === "yes"
                        ? "health-option expanded"
                        : "health-option"
                    }
                    key={name}
                  >

                    <div className="health-option-row">

                      <span>{label}</span>

                      <select
                        name={name}
                        value={form[name]}
                        onChange={handleChange}
                        required
                      >

                        <option value="">
                          Select
                        </option>

                        <option value="no">
                          No
                        </option>

                        <option value="yes">
                          Yes
                        </option>

                        <option value="prefer_not_to_say">
                          Prefer not to say
                        </option>

                      </select>

                    </div>


                    {form[name] === "yes" && (

                      <div className="condition-upload">

                        <label className="condition-dropzone">

                          <span className="condition-dropzone-title">
                            + Add reports for {label}
                          </span>

                          <small>
                            Optional. {hint}. PDF, JPG or PNG, up to{" "}
                            {MAX_FILES_PER_GROUP} files.
                          </small>

                          <input
                            type="file"
                            multiple
                            accept={ALLOWED_EXTENSIONS.join(",")}
                            onChange={(e) => handleConditionFiles(name, e)}
                          />

                        </label>

                        {fileErrors[name] && (
                          <p className="file-error">{fileErrors[name]}</p>
                        )}

                        {renderFileList(
                          conditionFiles[name] || [],
                          (index) => removeConditionFile(name, index)
                        )}

                      </div>

                    )}

                  </div>

                ))}

              </div>


              <div className="input-group">

                <label>
                  Other diagnosed conditions
                </label>

                <textarea
                  name="other_conditions"
                  placeholder="Optional"
                  value={
                    form.other_conditions
                  }
                  onChange={handleChange}
                  rows="4"
                />

              </div>

            </div>

          )}


          {/* STEP 4 */}

          {step === 4 && (

            <div className="form-step">

              <h2>Other documents</h2>

              <p className="step-description">
                Anything that doesn't belong to one condition,
                such as a full blood panel. Optional, up to
                {` ${MAX_FILES_PER_GROUP}`} files.
              </p>


              {failedUploads.length > 0 ? (

                <div className="upload-failures">

                  <strong>
                    Your profile is saved, but{" "}
                    {failedUploads.length === 1
                      ? "1 file"
                      : `${failedUploads.length} files`}{" "}
                    could not be uploaded:
                  </strong>

                  <ul>
                    {failedUploads.map(({ file, error: reason }, index) => (
                      <li key={index}>
                        {file.name}
                        {reason ? ` (${reason})` : ""}
                      </li>
                    ))}
                  </ul>

                  <span>
                    Try again, or skip and add them later from Reports.
                  </span>

                </div>

              ) : (

                <>

                  <label className="document-upload">

                    <div className="upload-icon">
                      +
                    </div>

                    <strong>
                      Upload other documents
                    </strong>

                    <span>
                      PDF, JPG or PNG, up to {MAX_FILE_MB} MB each
                    </span>

                    <input
                      type="file"
                      multiple
                      accept={ALLOWED_EXTENSIONS.join(",")}
                      onChange={handleDocuments}
                    />

                  </label>

                  {fileErrors.other && (
                    <p className="file-error">{fileErrors.other}</p>
                  )}

                  {renderFileList(documents, removeDocument)}

                </>

              )}

            </div>

          )}


          {/* Error */}

          {error && (

            <div className="form-error">
              {error}
            </div>

          )}


          {/* Navigation */}

          <div className="onboarding-actions">

            {step > 1 && !profileSaved && (

              <button
                type="button"
                className="back-button"
                onClick={previousStep}
              >
                ← Back
              </button>

            )}


            {failedUploads.length > 0 && (

              <button
                type="button"
                className="back-button"
                onClick={() => navigate("/dashboard")}
              >
                Skip for now
              </button>

            )}


            {step < 4 && (

              <button
                type="button"
                className="next-button"
                onClick={nextStep}
              >
                Continue →
              </button>

            )}


            {step === 4 && (

              <button
                type="submit"
                className="next-button"
                disabled={loading}
              >
                {loading
                  ? "Saving..."
                  : failedUploads.length > 0
                    ? "Retry upload →"
                    : "Complete profile →"}
              </button>

            )}

          </div>

        </form>

      </div>

    </div>
  );
}


export default OnboardingPage;