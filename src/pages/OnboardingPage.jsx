import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { completeProfile } from "../services/profile";

import "./OnboardingPage.css";


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


  const [documents, setDocuments] = useState([]);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");


  function handleChange(e) {

    setForm({
      ...form,
      [e.target.name]: e.target.value
    });

  }


  function handleDocuments(e) {

    setDocuments(
      Array.from(e.target.files)
    );

  }


  function nextStep() {

    setError("");

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

    setLoading(true);
    setError("");


    try {

      const user = JSON.parse(
        localStorage.getItem("movewell_user")
      );


      if (!user?.id) {

        throw new Error(
          "User information not found. Please sign in again."
        );

      }


      const formData = new FormData();


      formData.append(
        "user_id",
        user.id
      );


      Object.entries(form).forEach(
        ([key, value]) => {

          formData.append(
            key,
            value
          );

        }
      );


      documents.forEach(
        (document) => {

          formData.append(
            "documents",
            document
          );

        }
      );


      await completeProfile(
        formData
      );


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

                {[
                  ["diabetes", "Diabetes"],
                  ["hypertension", "Hypertension"],
                  ["heart_condition", "Heart condition"],
                  ["previous_injury", "Previous injury"],
                  ["joint_pain", "Current joint pain"],
                  ["back_neck_pain", "Back / neck pain"]
                ].map(([name, label]) => (

                  <div
                    className="health-option"
                    key={name}
                  >

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

              <h2>Health documents</h2>

              <p className="step-description">
                Upload relevant reports if you have them.
                These can later be used by our document
                analysis and RAG system.
              </p>


              <label className="document-upload">

                <div className="upload-icon">
                  +
                </div>

                <strong>
                  Upload health documents
                </strong>

                <span>
                  PDF, JPG or PNG
                </span>

                <input
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={handleDocuments}
                />

              </label>


              {documents.length > 0 && (

                <div className="selected-documents">

                  {documents.map(
                    (document, index) => (

                      <div
                        className="selected-document"
                        key={index}
                      >

                        <span>📄</span>

                        <div>

                          <strong>
                            {document.name}
                          </strong>

                          <small>
                            {(
                              document.size / 1024
                            ).toFixed(1)} KB
                          </small>

                        </div>

                      </div>

                    )
                  )}

                </div>

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

            {step > 1 && (

              <button
                type="button"
                className="back-button"
                onClick={previousStep}
              >
                ← Back
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